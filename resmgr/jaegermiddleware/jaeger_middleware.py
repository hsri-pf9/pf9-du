import logging

from jaeger_client import Config

logger = logging.getLogger('resmgr')
#logger = logging.getLogger(__name__)
tracer = None

class JaegerMiddleware(object):
    """
    A middleware meant for initialization of Jaeger tracer.
    """

    def __init__(self, app, conf):
        self.app = app
        self.conf = conf

    def __call__(self, environ, start_response):
        # Just pass it down the pipeline
        return self.app(environ, start_response)

def filter_factory(global_conf, **local_conf):
    """
    Paste setup method
    """

    conf = global_conf.copy()
    conf.update(local_conf)

    logger.info("Setting up Jaeger middleware")

    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    enable_logging = local_conf.get('config.logging', 'true').lower() == 'true'
    config = Config(
      config={
        # Log traces to the log file
        'logging': enable_logging,
        'local_agent': {
            # Where to report the samples
            'reporting_host': conf['config.local_agent.reporting_host'],
            'reporting_port': int(conf['config.local_agent.reporting_port']),

            # A web service that controls the behavior about each service and sampling frequency
            'sampling_host': conf['config.local_agent.sampling_host'],
            'sampling_port': int(conf['config.local_agent.sampling_port'])
        }
      },
      # Name of the service
      service_name = local_conf['service_name'],
      # Validate the configuration
      validate = bool(local_conf['validate']),
    )

    dummy_config = Config(
        config={ # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
            'reporter_batch_size': 1,
        },
        service_name = 'resmgr',
    )

    if str(conf['config.enable_tracing']).lower() == 'true' :
        # this also sets opentracing.tracer global variable
        tracer = config.initialize_tracer()
        logger.info("Jaeger tracer has been initialised")
    else:
        logger.info("Jaeger tracing is disabled")

    if str(conf['config.enable_tracing_client_hooks']).lower() == 'true' :
        #Install patches from client_hooks of opentracing_instrumentation
        install_all_patches()
        logger.info("Installed OpenTracing client hook patches to enable tracing in module like SQLAlchemy, requests, MySQLDB etc.")
    else:
        logger.info("Tracing of OpenTracing clients like SqlAchemy, requests etc. is disabled")

    def jaeger_middleware(app):
        return JaegerMiddleware(app, conf)

    return jaeger_middleware

