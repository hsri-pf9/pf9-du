#!/bin/sh

# so we're not hitting source tree mirrors after every single build

spec_file=$1
sources_output_dir=$2
source_bundle_version=$3

usage() {
    echo "Usage: $0 <spec file> <source output dir> <version>"
    exit 1
}

[ "x$spec_file" = "x" ] && usage
[ "x$sources_output_dir" = "x" ] && usage
[ "x$source_bundle_version" = "x" ] && usage

BUILD_CACHE_ROOT=~/.pf9-du-buildcache
BUNDLE_DIR="$spec_file-$source_bundle_version"

if [ -d $BUILD_CACHE_ROOT/$BUNDLE_DIR ]; then
    cp -R $BUILD_CACHE_ROOT/$BUNDLE_DIR/* $sources_output_dir
else
    mkdir -p $BUILD_CACHE_ROOT/$BUNDLE_DIR/
    spectool -g -S -C $sources_output_dir $spec_file || (
        echo "Could not retrieve all source files, eliminating build cache" >&2
        rm -rf $BUILD_CACHE_ROOT/$spec_file
        exit 1
    )
    cp -R $sources_output_dir/* $BUILD_CACHE_ROOT/$BUNDLE_DIR/
fi
