from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.auth.router import router as auth_router
from src.cargo.router import router as cargo_router
from src.catalog.router import router as catalog_router
from src.exceptions import AppException
from src.expenses.router import router as expenses_router
from src.inventory.router import router as inventory_router
from src.middlewares import register_middlewares
from src.parties.router import router as parties_router
from src.payments.router import router as payments_router
from src.purchasing.router import router as purchasing_router
from src.reporting.router import router as reporting_router
from src.sales.router import router as sales_router

app = FastAPI(title="Trading System")
register_middlewares(app)


@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(auth_router, prefix="/auth", tags=["auth"])
# purchasing_router/payments_router/catalog_router already carry their domain tag from build_crud_router
app.include_router(catalog_router, prefix="/catalog")
app.include_router(purchasing_router, prefix="/purchasing")
app.include_router(payments_router, prefix="/payments")
app.include_router(parties_router, prefix="/parties")
app.include_router(cargo_router, prefix="/cargo")
app.include_router(inventory_router, prefix="/inventory")
app.include_router(sales_router, prefix="/sales")
app.include_router(expenses_router, prefix="/expenses")
app.include_router(reporting_router, prefix="/reporting")
