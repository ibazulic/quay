#!/bin/bash

QUAYDIR=${QUAYDIR:-"/"}
QUAYPATH=${QUAYPATH:-"."}
QUAYCONF=${QUAYCONF:-"$QUAYPATH/conf"}
QUAYCONFIG=${QUAYCONFIG:-"$QUAYCONF/stack"}

cd $QUAYDIR
python $QUAYCONF/init/readonly/readonly.py
