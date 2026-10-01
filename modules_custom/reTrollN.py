# author: reTrollN
# version: 1.2.0
# description: ТЫ САМЫЙ КРУТОЙ В ШКОЛЕ

from __future__ import annotations

import random
from telethon import events
from core.lib.loader.module_base import ModuleBase, command, watcher
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Integer, Boolean


class reTrollN(ModuleBase):
    name = "reTrollN"
    version = "1.2.0"
    author = "@cryst4xlr"
    description = "ТЫ САМЫЙ КРУТОЙ В ШКОЛЕ"

    config = ModuleConfig(
        ConfigValue(
            "target_id",
            0,
            "ID цели",
            validator=Integer(default=0),
        ),
        ConfigValue(
            "enabled",
            False,
            "Включить автоответ",
            validator=Boolean(default=False),
        ),
    )

    phrases = [
        "ты как хуй без резинки, бесполезный и быстро выходишь из строя",
        "у тебя язык длинный, но пользоваться не умеешь",
        "твои мысли никуда не вытекают и никому не нужны",
        "ты даже не достоин того, чтобы я тратил на тебя слюну",
        "твоя мать сосёт так, что я начинаю верить в бесконечность",
        "ты родился от того, что твоя мать не смогла нормально отсосать",
        "твой папаша сдал тебя в аренду моему хую",
        "ты как дырка в презервативе, случайность которая портит всё",
        "тебе нужно только хуй в рот",
        "твоя мать настолько привыкла к моему члену, что даже дышит им",
        "ты даже оскорбить нормально не можешь, только хуй соси в углу",
        "от твоих слов хуй твердеет от смеха",
        "если бы тупость была спермой, ты бы затопил всю планету",
        "твой рот работает быстрее, чем твоя мать когда я расстёгиваю ширинку",
        "ты как член в анусе, не нужен но всё равно вставляешься",
        "ты настолько жалкий, что даже мой хуй тебя жалеет",
        "твоя мать сосёт так, что я думаю взять её на работу",
        "у тебя мозгов как у моего члена в холодной воде, ноль реакции",
        "ты как презерватив с дыркой, бесполезный и опасный",
        "твоя мать записалась ко мне на постоянный отсос",
        "ты даже оскорбить нормально не можешь, только хуй в рот и молчи",
        "твой папаша смотрел как я ебу твою мать и просил научить его стоять",
        "ты как член в банке, никому не нужен но всё равно торчишь",
        "я бы тебя выебал, но даже мой член знает меру",
        "твоя мать на моём члене визжит и просит ещё",
        "ты как хуй в рукаве, всё равно никто не боится",
        "твой рот открывается только чтобы вставить себе в глотку",
        "если бы член был твоим лучшим другом, он бы тебя предал",
        "твоя мать сказала что я лучший, а ты ошибка в системе",
        "ты как старая резинка, эластичность нулевая",
        "твой язык работает быстрее чем твой мозг",
        "ты даже не понимаешь насколько ты тупой",
        "твоя мать уже устала от тебя",
        "ты как пустое место, никому не нужен",
        "у тебя нет ни ума ни достоинства",
        "ты просто шум, который никто не слушает",
        "твои слова ничего не значат",
        "ты даже не смешной, просто жалкий",
        "твоя мать разочарована в тебе",
        "ты как сломанная игрушка, бесполезный",
    ]

    async def on_load(self):
        config_dict = await self.kernel.get_module_config(
            self.name, self.config.to_dict()
        )
        self.config.from_dict(config_dict)
        self.kernel.store_module_config_schema(self.name, self.config)
        self._target_id = self.config["target_id"]
        self._enabled = self.config["enabled"]

    @command("startans", doc_ru="<id> Начать отвечать цели", doc_en="<id> Start answering target")
    async def cmd_startans(self, event):
        args = self.args(event).args
        if not args:
            await self.edit(event, "Укажи ID цели: .startans 123456789")
            return
        
        try:
            target_id = int(args[0])
            self.config["target_id"] = target_id
            self.config["enabled"] = True
            await self.kernel.save_module_config(self.name, self.config.to_dict())
            self._target_id = target_id
            self._enabled = True
            await self.answer(event, f"понял принял теперь жирный у нас - {target_id}")
        except ValueError:
            await self.edit(event, "ID должен быть числом")

    @command("stopans", doc_ru="Остановить автоответ", doc_en="Stop answering")
    async def cmd_stopans(self, event):
        self.config["enabled"] = False
        await self.kernel.save_module_config(self.name, self.config.to_dict())
        self._enabled = False
        await self.answer(event, "Остановлено")

    @command("addphrase", doc_ru="<фраза> Добавить фразу", doc_en="<phrase> Add phrase")
    async def cmd_addphrase(self, event):
        args = self.args_raw(event).strip()
        if not args:
            await self.edit(event, "Укажи фразу: .addphrase текст")
            return
        
        self.phrases.append(args)
        await self.answer(event, f"Добавлено (всего: {len(self.phrases)})")

    @command("listphrases", doc_ru="Показать все фразы", doc_en="Show all phrases")
    async def cmd_listphrases(self, event):
        if not self.phrases:
            await self.edit(event, "Фраз нет")
            return
        
        text = "\n".join([f"{i+1}. {p}" for i, p in enumerate(self.phrases)])
        await self.answer(event, f"ВСЕ Фразы ({len(self.phrases)}):\n\n{text}")

    @command("delphrase", doc_ru="<номер> Удалить фразу", doc_en="<number> Delete phrase")
    async def cmd_delphrase(self, event):
        args = self.args(event).args
        if not args:
            await self.edit(event, "Укажи номер: .delphrase 5")
            return
        
        try:
            idx = int(args[0]) - 1
            if 0 <= idx < len(self.phrases):
                removed = self.phrases.pop(idx)
                await self.answer(event, f"Удалено: {removed}")
            else:
                await self.edit(event, "Неверный номер")
        except ValueError:
            await self.edit(event, "Введи число")

    @watcher(incoming=True)
    async def reply_watcher(self, event):
        if not self._enabled:
            return
        
        if not hasattr(event, "sender_id"):
            return
        
        if event.sender_id == self._target_id:
            phrase = random.choice(self.phrases)
            await event.reply(phrase)