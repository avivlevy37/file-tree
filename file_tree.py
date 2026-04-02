from os import devnull
from pathlib import Path
from typing import Any, Iterable, Generator

from rich.console import Console
from rich.tree import Tree


class FileTree(Tree):
    def __init__(self,
                 directory: Path,
                 *,
                 name: str = ".",
                 include: Iterable[Path] | None = None,
                 exclude: Iterable[Path] | None = None,
                 **kwargs: dict[str, Any]) -> None:
        super().__init__(name, **kwargs)

        assert directory.is_dir(), directory
        self.base_directory = directory

        for file in self._iter_relative(self.base_directory, include, exclude):
            node = self
            for part in file.parts:
                child: Tree
                children = {child.label: child for child in node.children}
                if part not in children:
                    children[part] = node.add(part)
                node = children[part]

    def __iter__(self) -> Generator[Path, None, None]:
        yield from self._iter_tree(self, self.base_directory)

    def __str__(self) -> str:
        with open(devnull, "w", encoding="utf-8") as out:
            console = Console(file=out, record=True)
            console.print(self)
            return console.export_text()

    def __repr__(self) -> str:
        return super().__repr__()

    @staticmethod
    def _validate_files(files: Iterable[Path], base_directory: Path) -> None:
        """
        :raises FileNotFoundError: If one of the entered files is
                                   a directory or does not exist.
        :raises AssertionError: If one of the entered files is
                                not under `base_directory`.
        """
        for file in files:
            if not file.is_file():
                raise FileNotFoundError(f"{file} is not a file!")
            assert file.is_relative_to(base_directory), (
                f"{file} is not under base directory: {base_directory}"
            )

    @staticmethod
    def _validate_excludes(exclude: Iterable[Path]) -> tuple[list[Path], list[Path]]:
        """
        :raises FileNotFoundError: If one of the excluded files
                                   does not exist.
        :return: (excluded_files, excluded_dirs)
        """
        excluded_files = []
        excluded_dirs = []
        for excluded in exclude:
            if excluded.is_file():
                excluded_files.append(excluded)
            elif excluded.is_dir():
                excluded_dirs.append(excluded)
            else:
                raise FileNotFoundError(f"{excluded} does not exist!")
        return excluded_files, excluded_dirs

    @classmethod
    def _iter_relative(cls,
                       directory: Path,
                       include: Iterable[Path] | None,
                       exclude: Iterable[Path] | None) -> Generator[Path, None, None]:
        if include is None:
            include = [file for file in directory.rglob("*") if file.is_file()]
        if exclude is None:
            exclude = []

        cls._validate_files(include, directory)
        excluded_files, excluded_dirs = cls._validate_excludes(exclude)

        for file in include:
            if file in excluded_files:
                continue
            if any(file.is_relative_to(excluded) for excluded in excluded_dirs):
                continue
            yield file.relative_to(directory)

    @classmethod
    def _iter_tree(cls,
                   node: Tree,
                   base_path: Path) -> Generator[Path, None, None]:
        node_path = base_path / str(node.label)
        if node_path.is_file():
            yield node_path
            return
        for child in node.children:
            yield from cls._iter_tree(child, node_path)
