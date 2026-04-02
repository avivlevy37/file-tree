from os import devnull
from pathlib import Path
from typing import Any, Callable, Iterable, Generator

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

        if include is not None:
            self._validate_files(include, directory)

        if exclude is None:
            exclude = []
        exclude: Iterable[Path]

        excluded_files, excluded_dirs = self._validate_excludes(exclude)

        files = self._iter_relative(
            directory=self.base_directory,
            include=include,
            exclude=excluded_files + excluded_dirs,
        )
        for file in files:
            assert self._add_to_tree(self, file) is not None

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
    def _add_to_tree(tree: Tree,
                     path: Path,
                     node_predicate: Callable[[Tree], bool] = lambda _: True) -> Tree | None:
        node = tree
        first_added: tuple[Tree, Tree] | None = None
        for part in path.parts:
            if not node_predicate(node):
                if first_added is not None:
                    node, added = first_added
                    node.children.remove(added)
                return None
            child: Tree
            children = {child.label: child for child in node.children}
            if part not in children:
                added = node.add(part)
                if first_added is None:
                    first_added = node, added
                children[part] = added
            node = children[part]
        return node

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

    @staticmethod
    def _iter_relative(directory: Path,
                       include: Iterable[Path] | None,
                       exclude: Iterable[Path]) -> Generator[Path, None, None]:
        def __iter_relative(
                _base: Path,
                _directory: Path,
                _include: Iterable[Path] | None,
                _exclude: Iterable[Path],
        ) -> Generator[Path, None, None]:
            if _directory in _exclude:
                return
            for _child in _directory.iterdir():
                if _child in _exclude:
                    continue
                if _child.is_dir():
                    yield from __iter_relative(
                        _base,
                        _child,
                        _include,
                        _exclude,
                    )
                    continue
                # child is a file
                if _include is not None and _child not in _include:
                    continue
                yield _child.relative_to(_base)

        yield from __iter_relative(directory, directory, include, exclude)

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
