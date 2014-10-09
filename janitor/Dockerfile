FROM centos:centos6
MAINTAINER dev@platform9.net

RUN yum install -y gcc python-setuptools
ADD  etc /etc
ADD  bin /usr/bin
ADD  . /opt/pf9/janitor

RUN mkdir -p /var/log/pf9
WORKDIR /opt/pf9/janitor
RUN python setup.py install

CMD ['python', '/usr/bin/run-janitor.py']
