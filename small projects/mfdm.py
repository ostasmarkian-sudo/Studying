from fastapi import FastAPI, Request, HTTPException, status
from fastapi.params import Body
from pydantic import BaseModel

app = FastAPI()


class Post(BaseModel):
    title: str
    content: str
    publiched: bool = True


@app.get(
    "/",
    include_in_schema=False,
)
def toolss():
    return {"title": "Hello World", "content": "fdssf"}


@app.get("/posts")
def data():
    return {"data": "this is your post"}


@app.post("/posts")
def create_post(new_post: Post):
    print(new_post.title, new_post.publiched)
    print(new_post.dict())
    if new_post.publiched == True:
        return {"data": new_post}
