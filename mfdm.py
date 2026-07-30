from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

tamples = Jinja2Templates(directory="tamples")
app = FastAPI()
tool: list[dict] = [
    {
        "id": 1,
        "tools": "hummer",
        "material": "iron",
        "prise": 57,
    },
]


@app.get(
    "/",
    include_in_schema=False,
)
def home(request: Request):
    return tamples.TemplateResponse(request, "home.html", {"tool": tool})


@app.get(
    "/tools",
)
def tools():
    return tool
