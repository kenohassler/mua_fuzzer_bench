# llvm-mutation-tool

## Mutation documentation

The file [mutation_doc.json](mutation_doc.json) contains a documentation about the different mutation types implemented
in this project as a machine readable json file.

## Install

### Docker Install
```shell script
# use the python script mutator-docker-wrapper.py

# first build the docker containers
python3 mutator-docker-wrapper.py -b

# then connect to the container
python3 mutator-docker-wrapper.py -a

# [optional] constul the script's help output for rebuilding and similar (will be faster than the initial build)
python3 mutator-docker-wrapper.py -h
```


### Local Install (only recommended for local development!)

```shell script
# run from root directory

# llvm installation on Mac:
brew install llvm@11

# llvm installation on linux:
echo deb http://apt.llvm.org/focal/ llvm-toolchain-focal-11 main >> /etc/apt/sources.list && \
    wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -

apt-get update && apt-get upgrade -y

apt-get install -y gcc-10 g++-10 gcc-10-plugin-dev gcc-10-multilib \
    libc++-10-dev gdb lcov

apt-get install -y clang-11 clang-tools-11 libc++1-11 libc++-11-dev \
    libc++abi1-11 libc++abi-11-dev libclang1-11 libclang-11-dev \
    libclang-common-11-dev libclang-cpp11 libclang-cpp11-dev liblld-11 \
    liblld-11-dev liblldb-11 liblldb-11-dev libllvm11 libomp-11-dev \
    libomp5-11 lld-11 lldb-11 llvm-11 llvm-11-dev llvm-11-runtime llvm-11-tools

update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 0
update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-10 0

rm -rf /var/cache/apt/archives/*

ln /bin/clang-11 /bin/clang
ln /bin/clang++-11 /bin/clang++
ln /bin/opt-11 /bin/opt
ln /bin/llvm-config-11 /bin/llvm-config
ln /bin/llvm-ar-11 /bin/llvm-ar



# compiles the project and installs it under build/install
export LD_LIBRARY_PATH=${mutation_tool_home}/build/install/LLVM_Mutation_Tool/lib/
gradle build
```


## Invoke Generation of Mutation Files
General invoke:
```shell script
# invokes the mutation pipeline, check for details on how to invoke the project in detail
./run_mutation.py [-bc] [-ll] [-bn] [-cpp] [-m <int>] <path-to-subject.c> (e.g. ./samples/simple_malloc/malloc.c) 
```
Explanation of optional arguments (at least one must be chosen, otherwise the output would be empty):
```
-bc: Keeps the mutated bitcode files.
-ll: Keeps the mutated bitcode files in human readable form.
-bn: Generates runnable binaries if possible.
-m <int>: Defines the mutation ID that should be applied, -1 for all mutations, 
    -2 or left out for just generation the mutationlocations file and a binary that prints
    covered mutations to the defined folder.
-cpp: Uses clang++ for compilation instead of clang.
```

**If a new mutant is generated all already generated mutants are deleted!**

## Running Mutated Programs

The mutated programs have code injected which prints if the mutation was triggered.
It is possible to influence the output by defining environment variables:

```shell
export TRIGGERED_OUTPUT="Some output." # can contain any string which will be printed to the command line 
    and written to the file TRIGGERED_FILE if it is defined and could be created; a default value is printed if
    this environment variable is not defined

export TRIGGERED_FOLDER="some/file/to/report/mutation/trigger_signal" # a path to a folder which will for each mutation UID
contain a file which indicates that the mutation was triggered. If not defined the files will be written to ./triggered_signal
```

Also, if one wants to test which mutations could be covered, a binary is generated when producing the mutants 
which will print all covered mutation locations:
Invoke the binary ```*.opt_mutate``` (e.g. [samples/simple_malloc/malloc.c.opt_mutate](samples/simple_malloc/malloc.c.opt_mutate)) in the respective subject folder, it will print all found locations during
the run as explained above.

## Clean
```shell script
# run in root directory to delete all build products
# can also be used if the build does not correctly update or another strange behavior is observed

gradle clean
```
```shell script
# run in root directory to delete all generated mutation files in samples

sh clean_mutations_in_samples.sh
```

# Running the Eval

This sections describes how to start an eval run.
The core eval functionality is implemented in `eval.py`, a convenience wrapper (`eval.sh`) for debian sets needed environment variables, prepares some directories and finally calls this python script.
Additionally there is `minimize_seeds.sh`, a script to download the seed files for the subjects and minimizes them.

## Pre-Requisites

To run the python scripts, `python3` as well as the `docker` package for python is needed.

For debian:
```
sudo apt install python3-pip
pip3 install docker
```

## Starting an Eval Run

TODO

## Adding New Subjects

TODO

## Adding New Fuzzers

TODO

