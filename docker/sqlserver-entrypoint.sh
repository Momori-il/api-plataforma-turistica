#!/bin/sh
set -eu
MSSQL_SA_PASSWORD="$(cat /run/secrets/sql_admin_password)"
export MSSQL_SA_PASSWORD
exec /opt/mssql/bin/launch_sqlservr.sh /opt/mssql/bin/sqlservr
