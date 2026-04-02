from os import devnull
from pathlib import Path
from typing import Any, Callable, Iterable, Generator

from rich.console import Console
from rich.tree import Tree


class FileTree(Tree):
    def __init__(self,
                 directory: Path,
                 *,
                 name: str | None = None,
                 include: Iterable[Path] | None = None,
                 exclude: Iterable[Path] | None = None,
                 ignore_dot_prefix: bool = True,
                 **kwargs: dict[str, Any]) -> None:
        assert directory.is_dir(), directory
        if name is None:
            name = directory.name or "."
        name: str
        super().__init__(name, **kwargs)
        self.base_directory = directory

        if include is not None:
            self._validate_files(include, directory)

        if exclude is not None:
            exclude = self._validate_excludes(directory, exclude)
        else:
            exclude = []
        exclude: Iterable[Path]

        files = self._iter_relative(
            directory=self.base_directory,
            include=include,
            exclude=exclude,
            ignore_dot_prefix=ignore_dot_prefix,
        )
        for file in files:
            added = self._add_to_tree(self, file)
            assert added is not None

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
    def _get_all_parents(path: Path) -> set[Path]:
        parents: set[Path] = set()
        current = path
        while True:
            parent = current.parent
            if parent == current:  # Reached root
                return parents
            parents.add(parent)
            current = parent

    @classmethod
    def _validate_excludes(cls,
                           base: Path,
                           exclude: Iterable[Path]) -> set[Path]:
        """
        :raises FileNotFoundError: If one of the excluded files
                                   does not exist.
        :return: (excluded_files, excluded_dirs)
        """
        excluded_files: set[Path] = set()
        excluded_dirs: set[Path] = set()
        for excluded in exclude:
            if excluded.is_file():
                excluded_files.add(excluded)
            elif excluded.is_dir():
                excluded_dirs.add(excluded)
            else:
                raise FileNotFoundError(f"{excluded} does not exist!")
            assert excluded.is_relative_to(base)

        # Refine unnecessary dupes
        excluded_dirs = {
            _dir for _dir in excluded_dirs
            if not cls._get_all_parents(_dir) & excluded_dirs
        }
        excluded_files = {
            file for file in excluded_files
            if not cls._get_all_parents(file) & excluded_dirs
        }
        return excluded_files | excluded_dirs

    @staticmethod
    def _iter_relative(directory: Path,
                       include: Iterable[Path] | None,
                       exclude: Iterable[Path],
                       ignore_dot_prefix: bool) -> Generator[Path, None, None]:
        base = directory

        def __iter_relative(_directory: Path) -> Generator[Path, None, None]:
            if _directory in exclude:
                return
            for _child in _directory.iterdir():
                if ignore_dot_prefix and _child.name.startswith("."):
                    continue
                if _child in exclude:
                    continue
                if _child.is_dir():
                    yield from __iter_relative(_child)
                    continue
                # child is a file
                if include is not None and _child not in include:
                    continue
                yield _child.relative_to(base)

        yield from __iter_relative(directory)

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
