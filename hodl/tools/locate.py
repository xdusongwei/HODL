import os
import sys


class LocateTools:
    ENVIRONMENT_KEY_PYTHON_PATH = 'PYTHONPATH'
    ENVIRONMENT_KEY_IDE_ROOTS = 'IDE_PROJECT_ROOTS'

    @classmethod
    def _build_path_list(cls) -> list:
        path_list = list()
        python_path_list = list()
        if cls.ENVIRONMENT_KEY_PYTHON_PATH in os.environ:
            python_path_list = os.environ[cls.ENVIRONMENT_KEY_PYTHON_PATH].split(":")
        if cls.ENVIRONMENT_KEY_IDE_ROOTS in os.environ:
            path_list.append(os.environ[cls.ENVIRONMENT_KEY_IDE_ROOTS])
        path_list.extend(python_path_list)
        path_list.extend(sys.path)
        return path_list

    @classmethod
    def locate_file(cls, file_path) -> str:
        path_list = cls._build_path_list()
        for path in path_list:
            detect_path = os.path.join(path, file_path)
            if os.path.isfile(detect_path):
                return detect_path
        raise FileNotFoundError

    @classmethod
    def locate_folder(cls, folder_path) -> str:
        path_list = cls._build_path_list()
        for path in path_list:
            detect_path = os.path.join(path, folder_path)
            if os.path.isdir(detect_path):
                return detect_path
        raise FileNotFoundError

    @classmethod
    def read_file(cls, path: str) -> None | str:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf8') as f:
                text = f.read()
            return text
        else:
            return None

    @classmethod
    def write_file(cls, path: str, text: str):
        with open(path, 'w', encoding='utf8') as f:
            f.write(text)


__all__ = ['LocateTools', ]
