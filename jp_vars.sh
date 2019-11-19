WHERE=$(dirname $0)

## CHANGE THIS!!!
ASTOOL_STORAGE=$WHERE/../../data/allstars

#export OLDPATH=$PATH
mkdir -p "$ASTOOL_STORAGE"

export ASTOOL_STORAGE=$(cd $ASTOOL_STORAGE && pwd)

#GADGETS=$WHERE/../../gadgets
#export GADGETS=$(cd $GADGETS && pwd)
#export PATH="$GADGETS:$PATH"

export ASTOOL_HOME=$(cd $WHERE && pwd)
export LIVE_MASTER_CHECK_ALLOWED=1

asunrc() {
    export PS1="$OLDPS1"
    #export PATH="$OLDPATH"

    #unset GADGETS
    unset ASTOOL_HOME
    unset ASTOOL_STORAGE
    unset OLDPS1
    #unset OLDPATH
    unset LIVE_MASTER_CHECK_ALLOWED

    unset -f asunrc
}

env | grep "ASTOOL_"
export OLDPS1="$PS1"
export PS1="@allstars:jp $PS1"

unset WHERE
echo "The environment was configured."
