FROM centos:7
MAINTAINER rdeuel@platform9.com

# python dependencies, apache and shibboleth
RUN yum install -y mysql-devel python-devel libffi-devel gcc

# install python code and supervisord
RUN curl https://bootstrap.pypa.io/get-pip.py |python -
COPY bblib-sdist.tgz \
     bbmaster-sdist.tgz \
     configutils-sdist.tgz \
     notifier-sdist.tgz \
     rabbitmgmt-sdist.tgz \
     resmgr-sdist.tgz \
     firkinize-sdist.tgz \
     upper-constraints.txt \
     /root/

WORKDIR /root
RUN pip install bblib-sdist.tgz \
                bbmaster-sdist.tgz \
                configutils-sdist.tgz \
                notifier-sdist.tgz \
                rabbitmgmt-sdist.tgz \
                resmgr-sdist.tgz \
                firkinize-sdist.tgz \
                supervisor \
                -c upper-constraints.txt \
                setuptools==33.1.1

# install confd
RUN curl -L https://github.com/kelseyhightower/confd/releases/download/v0.11.0/confd-0.11.0-linux-amd64 >/root/confd \
 && chmod 755 /root/confd \
 && mkdir -p /var/log/confd

COPY opt/ /opt/
COPY etc/ /etc/
COPY usr/ /usr/

# muster firmware is required for bbmaster
COPY pf9-muster-wrapper.rpm /root/
RUN yum install -y pf9-muster-wrapper.rpm

COPY init-region .
RUN chmod 755 /usr/bin/run-resmgr init-region

# destination dirs for confd-generated config files
RUN mkdir -p /opt/pf9/www/private/etc/pf9/certs/{ca,hostagent} /var/log/pf9

# bbmaster=8082, resmgr=8083
EXPOSE 8082 8083

CMD /usr/bin/supervisord
