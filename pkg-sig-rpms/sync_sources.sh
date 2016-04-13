#!/bin/sh

# so we're not hitting source tree mirrors after every single build

spec_file=$1
sources_output_dir=$2
source_bundle_version=${3:-1}

usage() {
    echo "Usage: $0 <spec file> <source output dir> <version>"
    exit 1
}

[ "x$spec_file" = "x" ] && usage
[ "x$sources_output_dir" = "x" ] && usage
[ "x$source_bundle_version" = "x" ] && usage

BUILD_CACHE_ROOT=~/.pf9-du-buildcache
BUNDLE_DIR="$spec_file-$source_bundle_version"

[ ! -d $BUILD_CACHE_ROOT ] && mkdir -p $BUILD_CACHE_ROOT
[ ! -d $sources_output_dir ] && mkdir -p $sources_output_dir

if [ -d $BUILD_CACHE_ROOT/$BUNDLE_DIR ]; then
    cp -R $BUILD_CACHE_ROOT/$BUNDLE_DIR/* $sources_output_dir
else
    mkdir -p $BUILD_CACHE_ROOT/$BUNDLE_DIR/
    if ! spectool -g -S -C $sources_output_dir $spec_file; then
        echo "Could not retrieve all source files, eliminating build cache" >&2
        rm -rf $BUILD_CACHE_ROOT/$BUNDLE_DIR
        exit 1
    fi
    cp -R $sources_output_dir/* $BUILD_CACHE_ROOT/$BUNDLE_DIR/
fi
