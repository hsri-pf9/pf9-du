# Notifier Library #

This library enables pf9 back-end services to publish object change messages
to the `pf9-changes` exchange on an AMQP broker. Those messages can then
be consumed by interested parties, such as user interfaces.

## Message format ##

A change message is a JSON object containing the type of change ('add', 'delete'
'change'), the type of object, and the object's ID.

Example:

    {
        "change_type": "change",
        "obj_type": "host",
        "obj_id": "45273-4523-6279"
    }

## Routing Key ##

Each message is sent with a routing key of the format `change_type.obj_type.obj_id`.
The `pf9-changes` exchange is a topic exchange, therefore consumers are free to
filter messages based on change type, object type, or object id, or any combination
thereof.

## API ##

    notifier.init(log, config)

Initializes the library with a log and configuration object.
The configuration object must contain an `amqp` section with the following
options:

- host
- username
- password
- virtual_host (optional)

It may optionally contain an `ssl` section with these options:

- certfile
- keyfile
- ca_certs


    notifier.publish_notification(change_type, obj_type, obj_id)

Queues a change message with the specified parameters.
The message is guaranteed to be delivered within one second.



