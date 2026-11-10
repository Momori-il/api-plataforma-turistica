#!/bin/sh
set -eu
umask 077
{ printf 'bind 0.0.0.0\nprotected-mode yes\nport 6379\nrequirepass '; cat /run/secrets/redis_password; printf '\nsave ""\nappendonly no\nmaxmemory 128mb\nmaxmemory-policy noeviction\n'; } > /tmp/redis.conf
exec redis-server /tmp/redis.conf
