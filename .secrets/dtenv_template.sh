#!/bin/bash
# A script to set various environment variables that DTBase reads. Many of these are
# secrets that you should not share openly, or e.g. commit to version control.
# This is a bash/shell script. If you are e.g. on Windows, you may need to adapt this to
# your platform (or use the Windows Subsystem for Linux).

# Test database
# You will need to set these to run the test suite. They set the PostgreSQL database the
# test suite connects to. Note that this database will get wiped every time the tests
# are run, so make sure you are not using it for anything else. A local PostgreSQL
# instance often works well.
export DT_SQL_TESTUSER="<REPLACE_ME>"
export DT_SQL_TESTPASS="<REPLACE_ME>"
export DT_SQL_TESTHOST="<REPLACE_ME>"
export DT_SQL_TESTPORT="<REPLACE_ME>"
export DT_SQL_TESTDBNAME="<REPLACE_ME>"

# Dev database
# You will need to set these to run a local instance of the DTBase backend using the
# `dtbase/backend/run.sh` script. They set the PostgreSQL database that the backend will
# use to store data.
export DT_SQL_USER="<REPLACE_ME>"
export DT_SQL_PASS="<REPLACE_ME>"
export DT_SQL_HOST="<REPLACE_ME>"
export DT_SQL_PORT="<REPLACE_ME>"
export DT_SQL_DBNAME="<REPLACE_ME>"

# Pulumi backend on Azure
# You will need to set these to be able to deploy DTBase on Azure using the Pulumi
# configuration in `infrastructure`. They specify the Azure storage account that will be
# used to store Pulumi's stack data. See `infrastructure/README.md` for more.
export AZURE_STORAGE_KEY="<REPLACE_ME>"
export AZURE_STORAGE_ACCOUNT="<REPLACE_ME>"
export AZURE_KEYVAULT_AUTH_VIA_CLI="true"

# Secrets for the web servers
# DT_DEFAULT_USER_PASS must be set to be able to run the test suite. DT_JWT_SECRET_KEY
# and DT_FRONT_SECRET_KEY will need to be set to run the backend and frontend,
# respectively, in a local deployment.
#
# DT_DEFAULT_USER_PASS is the password for the user `default_user@localhost`. You can
# log in as this default user when you've created a new DTBase instance, to create the
# first admin users. You should unset DT_DEFAULT_USER_PASS and comment it out from the
# secrets once you're done with the initial set up. This causes the default user to be
# deleted the next time the backend is restarted, plugging a possible security hole.
#
# The SECRET_KEY environment variables are private encryption keys for the JSON Web
# Tokens (JWT) generated by the backend and for the cookies set by the frontend for user
# management purposes. Anyone who has access to them can fake having admin access to
# your DTBase deployment, so make sure you set them to a non-trivial value (a long
# random string of characters is good) and keep them secret.
export DT_DEFAULT_USER_PASS="<REPLACE_ME>"
export DT_FRONT_SECRET_KEY="<REPLACE_ME>"
export DT_JWT_SECRET_KEY="<REPLACE_ME>"
