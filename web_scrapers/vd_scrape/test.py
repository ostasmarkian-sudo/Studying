import asyncio


class DatabaseExplodedError(Exception):
    pass


class ServerOnFireError(Exception):
    pass


class CoffeeNotFoundError(Exception):
    pass


async def check_database():
    await asyncio.sleep(1)
    raise DatabaseExplodedError(
        "PostgreSQL вибухнув. Таблиця users вилетіла у відкритий космос"
    )


async def check_server():
    await asyncio.sleep(1)
    raise ServerOnFireError("Температура сервера: 948°C. Викликаємо пожежників...")


async def check_programmer():
    await asyncio.sleep(1)
    raise CoffeeNotFoundError("КРИТИЧНА ПОМИЛКА: програміст працює без кави")


async def main():
    results = await asyncio.gather(
        check_database(),
        check_server(),
        check_programmer(),
        return_exceptions=True,
    )

    errors = [result for result in results if isinstance(result, Exception)]

    if errors:
        raise ExceptionGroup(
            "КАТАСТРОФІЧНИЙ ЗБІЙ УСІЄЇ ІНФРАСТРУКТУРИ",
            errors,
        )


asyncio.run(main())
