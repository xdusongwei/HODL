import os
import re
import sys
import pkgutil
import inspect
import importlib


class LocateTools:
    """
    文件系统定位工具
    帮助在 $PATH, IDE 和 $PYTHONPATH 等位置中搜索需要的文件和目录
    """
    ENVIRONMENT_KEY_PYTHON_PATH = 'PYTHONPATH'
    ENVIRONMENT_KEY_IDE_ROOTS = 'IDE_PROJECT_ROOTS'

    @classmethod
    def _build_path_list(cls) -> list:
        path_list = list()
        python_path_list = list()
        if cls.ENVIRONMENT_KEY_PYTHON_PATH in os.environ:
            python_path_list = os.environ[cls.ENVIRONMENT_KEY_PYTHON_PATH].split(':')
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
    def scan_folder(cls, folder_path, re_search: str) -> list[str]:
        result = list()
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if re.search(re_search, file.lower()):
                    path = os.path.join(root, file)
                    result.append(path)
        return result

    @classmethod
    def read_file(cls, path: str) -> None | str:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf8') as f:
                text = f.read()
            return text
        else:
            return None

    @classmethod
    def write_file(cls, path: str, text: str, mode: str = 'w'):
        args = dict(
            file=path,
            mode=mode,
        )
        if mode == 'w':
            args |= dict(encoding='utf8')
        with open(**args) as f:
            f.write(text)

    @classmethod
    def discover_plugins(cls, package_name):
        cls_list = list()
        package = importlib.import_module(package_name)
        for _, module_name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
            if ispkg:
                continue
            mod = importlib.import_module(module_name)
            members = inspect.getmembers(mod)
            for name, obj in members:
                if not inspect.isclass(obj):
                    continue
                if obj.__module__ != module_name:
                    continue
                cls_list.append(obj)
        return cls_list


__all__ = ['LocateTools', ]
