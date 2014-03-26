# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.


import pika
from pika.credentials import PlainCredentials

def io_loop(host,
            credentials,
            exch_name,
            state,
            before_processing_msgs_cb,
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

    def on_open(connection):
        state['connection'] = connection
        connection.channel(on_channel_open)

    def on_channel_open(channel):
        state['channel'] = channel
        channel.exchange_declare(exchange=exch_name,
                             exchange_type=exch_type,
                             callback=on_exchange_declare)

    def on_exchange_declare(method_frame):
        if not recv_keys:
            # Not consuming messages. Finish early.
            before_processing_msgs_cb()
            return
        state['channel'].queue_declare(callback=on_queue_declare,
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
    connection = pika.SelectConnection(pika.ConnectionParameters(host=host,
                        port=port,
                        credentials=credentials,
                        virtual_host=virtual_host,
                        ssl=ssl_options is not None,
                        ssl_options=ssl_options),
                    on_open_callback=on_open
                    )

    # Enter I/O loop
    connection.ioloop.start()
