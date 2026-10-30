
from pathlib import Path
import sys
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Make the project root importable when running with Uvicorn.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from food_detection import (
    analyze_fridge,
    validate_image,
    _get_food_category,
)


app = FastAPI(
    title="Fridge Scan API",
    description="API for fridge inventory, grocery lists, food scans, and recipes.",
    version="1.1.0",
)

# Development configuration. Restrict origins before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    quantity: float = Field(default=1, ge=0)
    unit: str = Field(default="item", min_length=1, max_length=30)
    category: str = Field(default="Other", max_length=80)
    low_stock_threshold: float = Field(default=1, ge=0)

class InventoryItemUpdate(BaseModel):
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)

class GroceryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    quantity: float = Field(default=1, gt=0)
    unit: str = Field(default="item", min_length=1, max_length=30)


class GroceryCheckUpdate(BaseModel):
    checked: bool

class GroceryItemUpdate(BaseModel):
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)

@app.on_event("startup")
def startup() -> None:
    database.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "fridge-scan-api"}


@app.get("/api/inventory")
def list_inventory():
    return database.get_inventory()


@app.post("/api/inventory", status_code=201)
def create_inventory_item(item: InventoryItemCreate):
    name = item.name.strip()
    unit = item.unit.strip()
    category = item.category.strip() or "Other"

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Item name cannot be empty.",
        )

    if not unit:
        raise HTTPException(
            status_code=400,
            detail="Item unit cannot be empty.",
        )

    try:
        database.add_inventory_item(
            name=name,
            quantity=item.quantity,
            unit=unit,
            category=category,
            low_stock_threshold=item.low_stock_threshold,
        )

        inventory = database.get_inventory()
        for saved_item in inventory:
            if saved_item["name"].casefold() == name.casefold():
                return saved_item

        raise HTTPException(
            status_code=500,
            detail=(
                "Item operation completed, but the saved item "
                "could not be retrieved."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.delete("/api/inventory/{item_id}")
def remove_inventory_item(item_id: int):
    existing_items = database.get_inventory()

    if not any(item["id"] == item_id for item in existing_items):
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found.",
        )

    database.delete_inventory_item(item_id)
    return {"deleted": True, "id": item_id}
@app.put("/api/inventory/{item_id}")
def edit_inventory_item(
    item_id: int,
    update: InventoryItemUpdate,
):
    unit = update.unit.strip()

    if not unit:
        raise HTTPException(
            status_code=400,
            detail="Inventory unit cannot be empty.",
        )

    try:
        result = database.update_inventory_quantity_unit(
            item_id,
            update.quantity,
            unit,
        )
        return {"updated": True, "item": result}
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

@app.get("/api/groceries")
def list_groceries():
    return database.get_grocery_items()


@app.post("/api/groceries", status_code=201)
def create_grocery_item(item: GroceryItemCreate):
    name = item.name.strip()
    unit = item.unit.strip()

    if not name or not unit:
        raise HTTPException(
            status_code=400,
            detail="Grocery name and unit cannot be empty.",
        )

    try:
        return database.add_grocery_item(
            name=name,
            quantity=item.quantity,
            unit=unit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.patch("/api/groceries/{item_id}")
def update_grocery_item(
    item_id: int,
    update: GroceryCheckUpdate,
):
    try:
        result = database.set_grocery_checked(
            item_id,
            update.checked,
        )
        return {"updated": True, "result": result}
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

@app.put("/api/groceries/{item_id}")
def edit_grocery_item(
    item_id: int,
    update: GroceryItemUpdate,
):
    try:
        result = database.update_grocery_item(
            item_id,
            update.quantity,
            update.unit,
        )
        return {"updated": True, "item": result}
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

@app.delete("/api/groceries/{item_id}")
def remove_grocery_item(item_id: int):
    try:
        result = database.delete_grocery_item(item_id)
        return {"deleted": True, "result": result}
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/api/recipes")
def list_recipes():
    return database.get_recipe_suggestions()

@app.post(
    "/api/scan",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary",
                                },
                                "description": (
                                    "Select one or more JPEG, PNG, "
                                    "or WEBP images"
                                ),
                            }
                        },
                    }
                }
            },
        }
    },
)
async def scan_fridge(
    files: Annotated[
        list[UploadFile],
        File(
            description="Select one or more JPEG, PNG, or WEBP images"
        ),
    ],
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one image.",
        )

    if len(files) > 8:
        raise HTTPException(
            status_code=400,
            detail="Upload a maximum of 8 images.",
        )

    image_bytes_list = []

    for uploaded_file in files:
        content_type = uploaded_file.content_type or ""

        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{uploaded_file.filename or 'File'} "
                    "is not an image."
                ),
            )

        image_bytes = await uploaded_file.read()

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{uploaded_file.filename or 'Image'} is empty.",
            )

        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Each image must be 10 MB or smaller.",
            )

        if not validate_image(image_bytes):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Could not read "
                    f"{uploaded_file.filename or 'image'}. "
                    "Please upload a valid JPEG, PNG, or WEBP image."
                ),
            )

        image_bytes_list.append(image_bytes)

    # One Groq request for the complete scan.
    try:
        analysis = analyze_fridge(image_bytes_list)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Log details on the server without returning internal errors.
        print(f"Unexpected fridge scan error: {type(exc).__name__}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during food recognition.",
        ) from exc

    detected_foods = []

    for item in analysis["inventory"]:
        name = item["item"].strip()

        if not name:
            continue

        # Use the shared categorizer from food_detection.py.
        category = _get_food_category(name)

        detected_foods.append(
            {
                "name": name,
                "quantity": 1,
                "unit": "item",
                "category": category,
                "quantity_status": item["quantity"],
            }
        )

    # Save detected foods, categories, and visual stock statuses.
    try:
        database.record_scan(detected_foods)
    except Exception as exc:
        print(f"Unexpected inventory-save error: {type(exc).__name__}")
        raise HTTPException(
            status_code=500,
            detail="Food recognition succeeded, but saving the inventory failed.",
        ) from exc

            # Save the AI-generated recipes.
    suggested_recipes = analysis.get("suggested_recipes", [])

    try:
       database.save_recipe_suggestions(suggested_recipes)
    except Exception as exc:
        print(f"Unexpected recipe-save error: {type(exc).__name__}")
        raise HTTPException(
            status_code=500,
            detail="The scan succeeded, but saving recipe suggestions failed.",
        ) from exc

    # Return the inventory as saved in the database.
    saved_inventory = database.get_inventory()

    return {
        "foods": detected_foods,
        "count": len(detected_foods),
        "inventory": saved_inventory,
        "low_stock_alerts": analysis["low_stock_alerts"],
        "suggested_recipes": suggested_recipes,
        "message": "Fridge scan completed using Groq AI.",
    }
