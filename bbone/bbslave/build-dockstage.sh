#!/bin/sh

DOCKSTAGE=$1

# .gnupg and .gpgpass have to exist, so create
# dummies if the user does not wish to go
# through the whole package signing routine.
function stage_deps() {
    local dockstage=$1
    if [ "x$SIGN_PACKAGES" = "x1" ]; then
        cp -R ~/.gnupg ${dockstage}/.gnupg
        rm -f ${dockstage}/.gnupg/S.gpg-agent
        cp ~/.rpmmacros ${dockstage}/.rpmmacros
        cp ~/.gpgpass ${dockstage}/.gpgpass
    else
        mkdir ${dockstage}/.gnupg
        touch ${dockstage}/.rpmmacros ${dockstage}/.gpgpass
    fi
}

mkdir -p $DOCKSTAGE
stage_deps $DOCKSTAGE
