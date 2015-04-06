# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.


import pika
from pika.exceptions import AMQPConnectionError
from pika.credentials import PlainCredentials

def io_loop(log,
            host,
            credentials,
            exch_name,
            state,
            before_processing_msgs_cb,
            queue_name,
            exch_type='direct',
            recv_keys=None,
            consume_cb=None,
            virtual_host=None,
            ssl_options=None):
    """
    Connects to AMQP broker and enters message processing loop
    :param str host: The broker host name or IP
    :param PlainCredentials credentials: The login credentials
    :param str exch_name: The exchange name
    :param dict state: A dictionary storing connection variables
    :param function before_processing_msgs_cb: A callback to call just before
     sending or receiving messages.
    :param str exch_type: The type of exchange (defaults to 'direct')
    :param list recv_keys: List of receive routing keys (optional)
    :param function consume_cb: A callback for consuming messages (optional)
    :param str virtual_host: Virtual host to be used in AMQP broker. Default is
     None (optional)
    :param dict ssl_options: SSL options if SSL is enabled (optional)
    """

    def add_on_connection_close_callback():
        """
        This method adds an on close callback that will be invoked by pika
        when RabbitMQ closes the connection to the publisher unexpectedly.
        """
        state['connection'].add_on_close_callback(on_connection_closed)

    def on_connection_closed(connection, reply_code, reply_text):
        """
        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will throw an error
        and rely on an outer loop to retry if necessary.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given
        """
        log.warn('Connection closed due to %s', reply_text)
        connection.ioloop.stop()
        state['closed_unexpectedly'] = True
        del state['connection']

    def on_open(connection):
        state['connection'] = connection
        add_on_connection_close_callback()
        connection.channel(on_channel_open)

    def on_channel_close(channel, reply_code, reply_text):
        log.warn('Channel closed due to %s', reply_text)
        del state['channel']

    def on_channel_open(channel):
        state['channel'] = channel
        channel.add_on_close_callback(on_channel_close)
        channel.exchange_declare(exchange=exch_name,
                                 exchange_type=exch_type,
                                 callback=on_exchange_declare)

    def on_exchange_declare(method_frame):
        if not recv_keys:
            # Not consuming messages. Finish early.
            before_processing_msgs_cb()
            return
        state['channel'].queue_declare(queue=queue_name,
                                       callback=on_queue_declare,
                                       exclusive=True)

    def on_queue_declare(method_frame):
        # This method would be called back multiple times if there are multiple
        # receive keys to be setup, but capture the queue_name only when the
        # queue has been declared initially.
        if 'queue_name' not in state:
            state['queue_name'] = method_frame.method.queue
        # Pop the first receive key from the recv_keys. If there are pending
        # keys in the list, callback to on_queue_declare to bind those keys as
        # well. If not, callback to on_queue_bind method
        recv_key = recv_keys.pop(0)
        cb_method = on_queue_declare if recv_keys else on_queue_bind

        state['channel'].queue_bind(exchange=exch_name,
                           queue=state['queue_name'],
                           routing_key=recv_key,
                           callback=cb_method)

    def on_queue_bind(method_frame):
        if before_processing_msgs_cb:
            before_processing_msgs_cb()
        state['channel'].basic_consume(consumer_callback=consume_cb,
                                       queue=state['queue_name'],
                                       no_ack=True)

    port = 5671 if ssl_options else 5672
    # NOTE: The connection below doesn't use socket timeout yet because the only
    # consumers of this io_loop call are services within the DU and being local to
    # rabbit, they don't have latency issues like services running on customer
    # site.
    connection = pika.SelectConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials,
                virtual_host=virtual_host,
                ssl=ssl_options is not None,
                ssl_options=ssl_options),
            on_open_callback=on_open)
    connection.ioloop.start()
    if 'closed_unexpectedly' in state:
        raise AMQPConnectionError


def dual_channel_io_loop(log,
                         host,
                         credentials,
                         queue_name,
                         retry_timeout,
                         connection_up_cb,
                         connection_down_cb,
                         send_channel_up_cb,
                         send_channel_down_cb,
                         consume_cb,
                         virtual_host=None,
                         ssl_options=None,
                         socket_timeout=None):
    """
    Connects to AMQP broker and enters message processing loop.
    Sets up 2 channels, one for sending, and the other for receiving.
    Automatically detects channel closure and re-opens it after a specified
    timeout. A basic_consume() with the specified queue name is automatically
    invoked on the receive channel. In contrast, the caller is responsible for
    calling basic_publish() on the send channel, choosing whatever exchange it
    desires.

    :param str host: The broker host name or IP
    :param PlainCredentials credentials: The login credentials
    :param str queue_name: Name of queue to receive from
    :param int retry_timeout: Seconds to wait before re-opening failed channel
    :param function connection_up_cb: Called when connection is open
    :param function connection_down_cb: Called when connection is closed
    :param function send_channel_up_cb: Called when ready to send messages
    :param function send_channel_down_cb: Called when no longer able to send
    :param function exchange_up_cb: Called when the exchange has been declared
    :param function consume_cb: A callback for consuming messages
    :param str virtual_host: Virtual host to be used in AMQP broker. Default is
     None (optional)
    :param dict ssl_options: SSL options if SSL is enabled (optional)
    """

    def on_connection_closed(connection, reply_code, reply_text):
        """
        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will throw an error
        and rely on an outer loop to retry if necessary.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given
        """
        log.warn('Connection closed due to %s, retrying in %d seconds',
                 reply_text, retry_timeout)
        connection_down_cb(connection)

    #--------------------------------------------------------------------------

    def on_open(connection):
        connection.add_on_close_callback(on_connection_closed)
        open_channel(connection, 'send',
                     send_channel_up_cb, send_channel_down_cb)
        # Make the recv channel less verbose w.r.t. close events, because
        # they will be common before a host is authorized
        open_channel(connection, 'recv', on_recv_channel_open,
                     warn_on_channel_close=False)
        connection_up_cb(connection)

    #--------------------------------------------------------------------------

    def open_channel(connection, name, channel_up_cb,
                     channel_down_cb=None,
                     warn_on_channel_close=True):

        def _retry():
            connection.channel(_on_channel_open)

        def _on_channel_open(channel):
            channel.add_on_close_callback(_on_channel_close)
            channel_up_cb(channel)

        def _on_channel_close(channel, reply_code, reply_text):
            logger('Channel "%s" closed due to %s, retrying in %d seconds',
                    name, reply_text, retry_timeout)
            if channel_down_cb:
                channel_down_cb(channel)
            connection.add_timeout(retry_timeout, _retry)

        logger = log.warn if warn_on_channel_close else log.debug
        _retry()

    #--------------------------------------------------------------------------

    def on_recv_channel_open(channel):
        channel.basic_consume(consumer_callback=consume_cb,
                              queue=queue_name,
                              no_ack=True)

    #--------------------------------------------------------------------------

    port = 5671 if ssl_options else 5672
    conn = pika.SelectConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials,
                virtual_host=virtual_host,
                ssl=ssl_options is not None,
                ssl_options=ssl_options,
                socket_timeout=socket_timeout),
            on_open_callback=on_open)
    conn.ioloop.start()
