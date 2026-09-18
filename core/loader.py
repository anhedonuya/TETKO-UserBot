import os
import sys
import importlib.util
import logging
import inspect
from telethon import events
from core.tetko import Module

logger = logging.getLogger("TETKO.Loader")

class ModuleLoader:
    def __init__(self, client, db=None, modules_dir: str = "modules"):
        self.client = client
        self.db = db
        self.modules_dir = modules_dir
        self.loaded_modules: Dict[str, Module] = {}

    async def load_all(self):
        if not os.path.exists(self.modules_dir):
            os.makedirs(self.modules_dir)

        for filename in os.listdir(self.modules_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                mod_name = filename[:-3]
                await self.load_module(mod_name)

    async def load_module(self, mod_name: str) -> bool:
        file_path = os.path.join(self.modules_dir, f"{mod_name}.py")
        if not os.path.exists(file_path):
            logger.error(f"Файл модуля не найден: {file_path}")
            return False

        try:
            spec = importlib.util.spec_from_file_location(f"modules.{mod_name}", file_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)

            for name, cls in inspect.getmembers(mod, inspect.isclass):
                if issubclass(cls, Module) and cls is not Module:
                    instance = cls(self.client, self.db)
                    await instance.on_load()
                    self._register_commands(instance)
                    self.loaded_modules[mod_name] = instance
                    logger.info(f"Загружен модуль TETKO KOMPAT: {instance.name} v{instance.version}")
                    return True

            logger.warning(f"В файле {mod_name}.py не найден класс модуля TETKO KOMPAT.")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки модуля {mod_name}: {e}", exc_info=True)
            return False

    def _register_commands(self, module_instance: Module):
        for attr_name in dir(module_instance):
            attr = getattr(module_instance, attr_name)
            if callable(attr) and getattr(attr, "__tetko_command__", False):
                cmd_name = attr.__cmd_name__ or attr_name.replace("_cmd", "").replace("cmd", "")
                prefix = attr.__cmd_prefix__
                pattern = f"^{re.escape(prefix)}{re.escape(cmd_name)}(?:\\s+(.*))?$"

                handler = self.client.add_event_handler(
                    attr,
                    events.NewMessage(outgoing=True, pattern=pattern)
                )
                module_instance.handlers.append((attr, handler))

    async def unload_module(self, mod_name: str) -> bool:
        if mod_name not in self.loaded_modules:
            return False

        instance = self.loaded_modules[mod_name]
        await instance.on_unload()

        for func, handler in instance.handlers:
            self.client.remove_event_handler(func, handler)

        del self.loaded_modules[mod_name]
        logger.info(f"Модуль {mod_name} выгружен.")
        return True
