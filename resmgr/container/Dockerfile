FROM  artifactory.platform9.horse/docker-local/pf9-py39-baseimg-alpine:stable
LABEL com.platform9.image-type=du

RUN apk update \
    && apk add \
     bash \
     curl \
     pkgconfig \
     gcc \
     g++ \
     dpkg \
     musl-dev \
     libressl-dev==3.5.3 \ 
     mariadb \
     --no-cache mariadb-dev \
     mariadb-client \
     mariadb-connector-c-dev \
     python3-dev \
     libffi-dev --force-broken-world

COPY bblib-sdist.tgz \
     bbmaster-sdist.tgz \
     configutils-sdist.tgz \
     notifier-sdist.tgz \
     rabbitmgmt-sdist.tgz \
     resmgr-sdist.tgz \
     upper-constraints.txt \
     /root/

WORKDIR /root

RUN pip install cryptography==41.0.4 \
                bblib-sdist.tgz

RUN pip install bbmaster-sdist.tgz
RUN pip install configutils-sdist.tgz \
                notifier-sdist.tgz \
                rabbitmgmt-sdist.tgz \
                -c upper-constraints.txt \
                setuptools==68.2.2

RUN pip install resmgr-sdist.tgz \
                -c upper-constraints.txt

COPY opt/ /opt/
COPY etc/ /etc/
COPY usr/ /usr/

# copy pf9-support files
COPY pf9-support-*.deb /opt/pf9/www/private/
COPY pf9-support-*.rpm /opt/pf9/www/private/
COPY pf9-support-role.json ./
RUN export pf9_version=$(cat ./pf9-support-role.json | python -c 'import json,sys; print (json.load(sys.stdin)["role_version"])') \
&& mkdir -p /etc/pf9/resmgr_roles/pf9-support/$pf9_version-1 \
&& mv pf9-support-role.json /etc/pf9/resmgr_roles/pf9-support/$pf9_version-1

COPY init-region .
RUN chmod 755 /usr/bin/run-resmgr init-region

RUN bash -c 'mkdir -p /opt/pf9/www/private/etc/pf9/certs/{ca,hostagent} /var/log/pf9  /var/metrics-db/pf9-resmgr'
RUN mkdir -p /etc/pf9/resmgr_roles/conf.d

# bbmaster=8082, resmgr=8083
EXPOSE 8082 8083

CMD supervisord

ARG VERSION
LABEL com.platform9.pf9_version=${VERSION}
ARG BUILD_ID
LABEL com.platform9.build=${BUILD_ID}
LABEL com.platform9.version="${VERSION}-${BUILD_ID}"
ARG BRANCH
LABEL com.platform9.branch=${BRANCH}
ARG APP_METADATA
LABEL com.platform9.app_metadata=${APP_METADATA}
