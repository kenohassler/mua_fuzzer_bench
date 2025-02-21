import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, TypedDict

from data_types import CompileArg, Fuzzer, Program

from constants import BLOCK_SIZE, IN_DOCKER_SHARED_DIR, SHARED_DIR

logger = logging.getLogger(__name__)


def fuzzer_container_tag(name: str) -> str:
    return f"mutation-testing-fuzzer-{name}"


def subject_container_tag(name: str) -> str:
    return f"mutation-testing-subject-{name}"


def mutation_locations_path(prog_info: Program) -> Path:
    orig_bc = Path(prog_info.orig_bc)
    return orig_bc.with_suffix('.ll.mutationlocations')


def mutation_locations_graph_path(prog_info: Program) -> Path:
    orig_bc = Path(prog_info.orig_bc)
    return orig_bc.with_suffix('.ll.mutationlocations.graph')


def mutation_detector_path(prog_info: Program) -> Path:
    orig_bc = Path(prog_info.orig_bc)
    return  orig_bc.with_suffix(".ll.opt_mutate")


def mutation_prog_source_path(prog_info: Program) -> Path:
    orig_bc = Path(prog_info.orig_bc)
    return orig_bc.with_suffix('.ll.ll')


def hash_file(file_path: Path) -> str:
    h = hashlib.sha512()
    b  = bytearray(BLOCK_SIZE)
    mv = memoryview(b)
    with open(file_path, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def shared_dir_to_docker(dir: Path) -> Path:
    rel_path = dir.relative_to(SHARED_DIR)
    res = IN_DOCKER_SHARED_DIR/rel_path
    return res


def get_seed_dir(seed_base_dir: Path, prog: str, fuzzer: str) -> Path:
    """
    Gets the seed dir inside of seed_base_dir based on the program name.
    Further if there is a directory inside with the name of the fuzzer, that dir is used as the seed dir.
    Example:
    As a sanity check if seed_base_dir/<prog> contains files and directories then an error is thrown.
    seed_base_dir/<prog>/<fuzzer> exists then this dir is taken as the seed dir.
    seed_base_dir/<prog> contains only files, then this dir is the seed dir.
    """
    prog_seed_dir = seed_base_dir/prog
    seed_paths = list(prog_seed_dir.glob("*"))
    has_files = any(sp.is_file() for sp in seed_paths)
    has_dirs = any(sp.is_dir() for sp in seed_paths)
    if has_files and has_dirs:
        raise ValueError(f"There are files and directories in {prog_seed_dir}, either the dir only contains files, "
              f"in which case all files are used as seeds for every fuzzer, or it contains only directories. "
              f"In the second case the content of each fuzzer directory is used as the seeds for the respective fuzzer.")

    if has_dirs:
        # If the fuzzer specific seed dir exists, return it.
        prog_fuzzer_seed_dir = prog_seed_dir/fuzzer
        if not prog_fuzzer_seed_dir.is_dir():
            logger.warning(f"WARN: Expected seed dir to exist {prog_fuzzer_seed_dir}, using full dir instead: {prog_seed_dir}")
            return prog_seed_dir
        return prog_fuzzer_seed_dir

    elif has_files:
        # Else just return the prog seed dir.
        return prog_seed_dir

    # Has no content
    else:
        raise ValueError(f"Seed dir has not content. {prog_seed_dir}")


class CoveredFile:
    def __init__(self, workdir: Path, start_time: float) -> None:
        super().__init__()
        self.found: Dict[int, float] = {}
        self.host_path = SHARED_DIR/"covered"/workdir
        self.host_path.mkdir(parents=True)
        self.docker_path = IN_DOCKER_SHARED_DIR/"covered"/workdir
        self.start_time = start_time

    def check(self) -> Dict[int, float]:
        cur_time = time.time() - self.start_time
        cur = set(int(cf.stem) for cf in self.host_path.glob("*"))
        new_keys = cur - self.found.keys()
        new = {nn: cur_time for nn in new_keys}
        self.found = {**self.found, **new}
        return new

    # def file_path(self):
    #     return self.path

    def __del__(self) -> None:
        shutil.rmtree(self.host_path)


def load_fuzzers() -> Dict[str, Fuzzer]:

    class FuzzerConfig(TypedDict):
        queue_dir: str
        queue_ignore_files: list[str]
        crash_dir: str
        crash_ignore_files: list[str]

    fuzzers = {}
    for fuzzer_dir in Path("dockerfiles/fuzzers").iterdir():
        if fuzzer_dir.name.startswith("."):
            continue # skip hidden files

        if fuzzer_dir.name == "system":
            continue

        if not fuzzer_dir.is_dir():
            continue
        
        fuzzer_config_path = fuzzer_dir/"config.json"
        with open(fuzzer_config_path, "r") as f:
            fuzzer_config: FuzzerConfig = json.load(f)

        fuzzer_name = fuzzer_dir.name

        fuzzers[fuzzer_name] = Fuzzer(
            name=fuzzer_name,
            queue_dir=fuzzer_config['queue_dir'],
            queue_ignore_files=fuzzer_config['queue_ignore_files'],
            crash_dir=fuzzer_config['crash_dir'],
            crash_ignore_files=fuzzer_config['crash_ignore_files'],
        )

    return fuzzers


def load_programs() -> Dict[str, Program]:

    class ProgramConfigArg(TypedDict):
        val: str
        action: Optional[str]

    class ProgramConfig(TypedDict):
        bc_compile_args: List[ProgramConfigArg]
        bin_compile_args: List[ProgramConfigArg]
        dict: str
        is_cpp: bool
        orig_bin: str
        orig_bc: str
        omit_functions: List[str]


    programs = {}
    for prog_dir in Path("dockerfiles/programs").iterdir():
        prog_dir_name = prog_dir.name
        if prog_dir_name.startswith("."):
            continue # skip hidden files

        if prog_dir_name == "common":
            continue

        if not prog_dir.is_dir():
            continue
        
        prog_config_path = prog_dir/"config.json"
        with open(prog_config_path, "r") as f:
            prog_config: Dict[str, ProgramConfig] = json.load(f)

        for prog_config_name, prog_config_data in prog_config.items():

            prog_name = f"{prog_dir_name}_{prog_config_name}"

            assert prog_name not in programs

            try:
                bc_compile_args = [
                    CompileArg(arg['val'], arg['action'])
                    for arg in prog_config_data["bc_compile_args"]
                ]

                bin_compile_args = [
                    CompileArg(arg['val'], arg['action'])
                    for arg in prog_config_data["bin_compile_args"]
                ]

                dict_path_str = prog_config_data["dict"]
                if dict_path_str is not None:
                    dict_path = Path("tmp/programs")/prog_dir_name/dict_path_str
                else:
                    dict_path = None

                programs[prog_name] = Program(
                    name=prog_name,
                    bc_compile_args=bc_compile_args,
                    bin_compile_args=bin_compile_args,
                    is_cpp=prog_config_data["is_cpp"],
                    dict_path=dict_path,
                    orig_bin=Path("tmp/programs")/prog_dir_name/prog_config_data["orig_bin"],
                    orig_bc=Path("tmp/programs")/prog_dir_name/prog_config_data["orig_bc"],
                    omit_functions=prog_config_data["omit_functions"],
                    dir_name=prog_dir_name,
                )
            except KeyError as e:
                raise KeyError(f"Key {e} not found in {prog_config_path}")

    return programs
