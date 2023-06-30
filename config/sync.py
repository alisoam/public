#! /bin/env python3

import abc
import argparse
import difflib
import filecmp
import itertools
import os
import shutil
from collections.abc import Iterable, Iterator, Generator, Sequence
from dataclasses import dataclass, field, InitVar
from pathlib import Path

import colorama


class ColorDiff(Iterable[str]):
    def __init__(self, diff: Iterator[str]):
        self.diff = diff

    def __iter__(self) -> Generator[str, None, None]:
        for line in self.diff:
            if line.startswith("+++ ") or line.startswith("--- "):
                continue

            match line[0]:
                case "+":
                    yield colorama.Fore.GREEN + line + colorama.Fore.RESET
                case "-":
                    yield colorama.Fore.RED + line + colorama.Fore.RESET
                case "@":
                    yield line


class SyncException(Exception):
    ...


class HostPathNotExistException(SyncException):
    def __init__(self, path: Path):
        self.path = path


class DiffException(SyncException):
    def __init__(self, path: Path, diff: Iterable[str]):
        self.path = path
        self.diff = diff


@dataclass
class Config(abc.ABC):
    name: str
    repo: InitVar[str]
    host: InitVar[str]
    sudo: bool = False

    host_path: Path = field(init=False)
    repo_path: Path = field(init=False)

    def __post_init__(self, repo: str, host: str):
        self.repo_path = Path(repo).absolute()
        self.host_path = Path(os.path.expanduser(host)).absolute()

    @abc.abstractmethod
    def check(self):
        ...

    @abc.abstractmethod
    def sync_host(self):
        ...

    @abc.abstractmethod
    def sync_repo(self):
        ...

    @staticmethod
    def file_diff(repo: Sequence[str], host: Sequence[str]) -> Iterable[str]:
        diff = difflib.unified_diff(host, repo)
        return ColorDiff(diff)

    @classmethod
    def file_check(cls, repo_path: Path, host_path: Path):
        assert repo_path.is_file()

        if not host_path.exists() or not host_path.is_file():
            raise HostPathNotExistException(host_path)

        if filecmp.cmp(repo_path, host_path):
            return

        with (
            open(repo_path, "r") as repo_file,
            open(host_path, "r") as host_file,
        ):
            diff = cls.file_diff(repo=repo_file.readlines(), host=host_file.readlines())
            raise DiffException(repo_path, diff)

    @staticmethod
    def file_sync_repo(repo_path: Path, host_path: Path):
        assert host_path.exists() and host_path.is_file()

        if host_path.exists() and filecmp.cmp(repo_path, host_path):
            return

        shutil.copy(host_path, repo_path)

    @staticmethod
    def file_sync_host(repo_path: Path, host_path: Path):
        assert repo_path.exists() and repo_path.is_file()
        if not host_path.parent.exists():
            host_path.parent.mkdir(parents=True)

        if host_path.exists() and filecmp.cmp(repo_path, host_path):
            return

        shutil.copy(repo_path, host_path)

    @classmethod
    def walk(cls, path: Path):
        assert path.is_dir()
        for p in path.iterdir(): 
            if p.is_dir():
                yield from cls.walk(p)
                continue

            yield p.resolve()


class File(Config):
    def check(self):
        self.file_check(repo_path=self.repo_path, host_path=self.host_path)

    def sync_repo(self):
        self.file_sync_repo(repo_path=self.repo_path, host_path=self.host_path)

    def sync_host(self):
        self.file_sync_host(host_path=self.host_path, repo_path=self.repo_path)


@dataclass
class Directory(Config):
    def check(self):
        exceptions: list[Exception] = []
        for repo_path in self.walk(self.repo_path):
            host_path = self.host_path / repo_path.relative_to(self.repo_path)
            try:
                self.file_check(host_path=host_path, repo_path=repo_path)
            except Exception as exc:
                exceptions.append(exc)

        match len(exceptions):
            case 0:
                pass
            case 1:
                raise exceptions[0]
            case _:
                raise ExceptionGroup("check exception", exceptions)

    def sync_repo(self):
        for repo_path in self.walk(self.repo_path):
            host_path = self.host_path / repo_path.relative_to(self.repo_path)
            self.file_sync_repo(repo_path=repo_path, host_path=host_path)

    def sync_host(self):
        for repo_path in self.walk(self.repo_path):
            host_path = self.host_path / repo_path.relative_to(self.repo_path)
            self.file_sync_host(repo_path=repo_path, host_path=host_path)


all_configs: list[Config] = [
    File("tmux", "tmux/tmux.conf", "~/.tmux.conf"),

    File("shell", "shell/zshrc", "~/.zshrc"),
    File("shell", "shell/bashrc", "~/.bashrc"),
    File("shell", "shell/profile", "~/.profile"),

    Directory("ssh", "ssh", "~/.ssh"),

    Directory("nvim", "nvim", "~/.config/nvim"),

    File("git", "git/gitconfig", "~/.gitconfig"),
    File("git", "git/gitignore", "~/.gitignore"),

    File("i3", "i3/i3", "~/.config/i3/config"),
    File("i3", "i3/i3status", "~/.config/i3status/config"),

    Directory("kitty", "kitty", "~/.config/kitty"),

#    File("docker", "docker/daemon.json", "/etc/docker/daemon.json", True),
#    File("docker", "docker/proxy.conf", "/etc/systemd/system/docker.service.d/proxy.conf", True),
]


def configs(names: list[str]) -> Iterator[tuple[str, Iterator[Config]]]:
    def key(config: Config) -> str:
        return config.name

    for name, config_group in itertools.groupby(sorted(all_configs, key=key), key=key):
        if name not in names:
            continue

        yield (name, config_group)


def check(names: list[str]):
    print("checking")
    for name, config_group in configs(names):
        print("---")
        print("@", name)

        for config in config_group:
            try:
                config.check()
            except* HostPathNotExistException as excs:
                for exc in excs.exceptions:
                    print(f"    '{exc.path}': Host file does not exist.")
            except* DiffException as excs:
                for exc in excs.exceptions:
                    print(f"    '{exc.path}': Host and repo files are different.")
                    for d in exc.diff:
                        print("        ", d, end="")


def sync_repo(names: list[str]):
    print("synchronizing repo")
    for name, config_group in configs(names):
        print("---")
        print("@", name)

        for config in config_group:
            config.sync_repo()


def sync_host(names: list[str]):
    print("synchronizing host")
    for name, config_group in configs(names):
        print("---")
        print("@", name)

        for config in config_group:
            config.sync_host()


def run():
    ACTIONS = dict(
        check=check,
        sync_repo=sync_repo,
        sync_host=sync_host,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("action", type=str, choices=ACTIONS.keys(), help="Action to do.")
    parser.add_argument(
        "-n", "--name",
        type=lambda s: s.split(","),
        default=[cfg.name for cfg in all_configs],
        help=f"Comma separated list of configs. Could be any of {','.join(set(cfg.name for cfg in all_configs))}.",
    )
    args = parser.parse_args()

    ACTIONS[args.action](args.name)


if __name__ == "__main__":
    run()
