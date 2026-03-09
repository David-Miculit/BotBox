import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

def main():
    uvicorn.run("main:app", host='0.0.0.0', port = 8000, reload=True)

if __name__ == "__main__":
    main()
