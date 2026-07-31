from fastapi import FastAPI, Request, HTTPException, status
from fastapi.templating import Jinja2Templates

tamples = Jinja2Templates(directory="tamples")
app = FastAPI()
tools: list[dict] = [
    {
        "id": 1,
        "tools": "hummer",
        "material": "iron",
        "prise": 57,
    },
    {
        "id": 2,
        "tools": "picture",
        "material": "diamond",
        "prise": 637,
    },
]


@app.get(
    "/",
    include_in_schema=False,
)
def home(request: Request):
    return tamples.TemplateResponse(
        request, "home.html", {"tool": tools, "title": "home"}
    )


@app.get(
    "/tools/",
)
def toolss():
    return tools


@app.get("/tools/{tools_id}")
def get_post(tools_id: int):
    for tool in tools:
        if tool.get("id") == tools_id:
            return tool
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
