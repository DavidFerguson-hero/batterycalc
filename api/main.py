from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import analyse, tariffs, batteries, solar, epc


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Battery Storage Calculator API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                          # Next.js dev
        "http://localhost:8080",                          # local static dev
        "https://davidferguson-hero.github.io",           # GitHub Pages
        "https://batterycalc.vercel.app",                 # Vercel
        "https://batterysizer.co.uk",                     # Custom domain
        "https://www.batterysizer.co.uk",                 # Custom domain (www)
        "https://dev.batterysizer.co.uk",                 # Dev subdomain
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse.router,   prefix="/api")
app.include_router(tariffs.router,   prefix="/api")
app.include_router(batteries.router, prefix="/api")
app.include_router(solar.router,     prefix="/api")
app.include_router(epc.router,       prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
