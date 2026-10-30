import { useEffect, useRef, useState } from "react";
import {
  Camera,
  LayoutDashboard,
  Refrigerator,
  ShoppingBasket,
  ChefHat,
  ScanLine,
  Search,
  Plus,
  Upload,
  Trash2,
  Check,
  AlertTriangle,
  Leaf,
  RefreshCw,
  Clock3,
  Sparkles,
  Menu,
  X,
  ImagePlus,
  ArrowUpRight,
} from "lucide-react";
import "./App.css";

const API = "http://127.0.0.1:8000/api";

const navigation = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "inventory", label: "My inventory", icon: Refrigerator },
  { id: "scan", label: "Scan my fridge", icon: ScanLine },
  { id: "groceries", label: "Grocery list", icon: ShoppingBasket },
  { id: "recipes", label: "Recipes", icon: ChefHat },
];

function stockLabel(item) {
  const status = String(item.visual_stock_status || "").toLowerCase();

  if (["low", "medium", "full"].includes(status)) {
    return status[0].toUpperCase() + status.slice(1);
  }

  const quantity = Number(item.quantity);

  return quantity <= Number(item.low_stock_threshold ?? 1)
    ? "Low"
    : "Available";
}

function App() {
  const [introPlaying, setIntroPlaying] = useState(true);
  const introVideoRef = useRef(null);

  const [page, setPage] = useState("dashboard");
  const [inventory, setInventory] = useState([]);
  const [groceries, setGroceries] = useState([]);
  const [recipes, setRecipes] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [newFood, setNewFood] = useState("");
  const [newFoodQuantity, setNewFoodQuantity] = useState("1");
  const [newFoodUnit, setNewFoodUnit] = useState("item");
  const [newGrocery, setNewGrocery] = useState("");
  const [newGroceryQuantity, setNewGroceryQuantity] = useState("1");
  const [newGroceryUnit, setNewGroceryUnit] = useState("item");
  const [pendingRecipeIngredients, setPendingRecipeIngredients] = useState([]);
  const [recipeGroceryTitle, setRecipeGroceryTitle] = useState("");
  const [addingRecipeGroceries, setAddingRecipeGroceries] = useState(false);
  const [files, setFiles] = useState([]);
  const [filePreviews, setFilePreviews] = useState([]);

  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [mobileMenu, setMobileMenu] = useState(false);

  const fileInput = useRef(null);
  const cameraInput = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Camera state declarations must come before effects that use them.
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");

  // Attach the webcam stream after React renders the video element.
  useEffect(() => {
    if (!cameraOpen || !videoRef.current || !streamRef.current) {
      return;
    }

    videoRef.current.srcObject = streamRef.current;

    videoRef.current.play().catch(() => {
      setCameraError("Unable to start the webcam preview.");
    });
  }, [cameraOpen]);

  // Stop the webcam whenever the component unmounts.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, options);

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${response.status})`);
    }

    if (response.status === 204) return null;

    return response.json();
  }

  async function loadData() {
    setError("");

    try {
      const [inv, shop, meal] = await Promise.all([
        request("/inventory"),
        request("/groceries"),
        request("/recipes"),
      ]);

      setInventory(
        Array.isArray(inv) ? inv : inv.items || inv.inventory || []
      );

      setGroceries(
        Array.isArray(shop) ? shop : shop.items || shop.groceries || []
      );

      setRecipes(
        Array.isArray(meal) ? meal : meal.recipes || meal.items || []
      );
    } catch (err) {
      setError(`${err.message}. Check that the Python backend is running.`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
  const previews = files.map((file) => ({
    name: file.name,
    url: URL.createObjectURL(file),
  }));

  setFilePreviews(previews);

  return () => {
    previews.forEach((preview) => URL.revokeObjectURL(preview.url));
  };
}, [files]);
  const lowStock = inventory.filter((item) =>
    ["low"].includes(stockLabel(item).toLowerCase())
  );

  const pendingGroceries = groceries.filter((item) => !item.checked);

  const visibleInventory = inventory.filter((item) =>
    String(item.name || "").toLowerCase().includes(search.toLowerCase())
  );

  async function addFood(event) {
    event.preventDefault();

    if (!newFood.trim()) return;

    try {
      await request("/inventory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newFood.trim(),
          quantity: Number(newFoodQuantity),
          unit: newFoodUnit,
          category: "Other",
        }),
      });

      setNewFood("");
      setNewFoodQuantity("1");
      setNewFoodUnit("item");
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteFood(id) {
    try {
      await request(`/inventory/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }
  async function editInventory(id, quantity, unit) {
  try {
    await request(`/inventory/${id}`, {
      method: "PUT",
      body: JSON.stringify({ quantity, unit }),
    });

    await loadData();
  } catch (err) {
    setError(err.message);
  }
}
  async function addGrocery(event) {
  event.preventDefault();

  if (!newGrocery.trim()) return;

  const quantity = Number(newGroceryQuantity);

  if (!Number.isFinite(quantity) || quantity <= 0) {
    setError("Please enter a valid quantity.");
    return;
  }

  try {
    await request("/groceries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newGrocery.trim(),
        quantity,
        unit: newGroceryUnit,
      }),
    });

    setNewGrocery("");
    setNewGroceryQuantity("1");
    setNewGroceryUnit("item");

    await loadData();
  } catch (err) {
    setError(err.message);
  }
}
  function prepareRecipeGroceries(recipe) {
  const missing = Array.isArray(recipe.additional_ingredients_needed)
    ? recipe.additional_ingredients_needed
    : [];

  if (missing.length === 0) return;

  const ingredients = missing.map((ingredient) => ({
    name: typeof ingredient === "string"
      ? ingredient
      : ingredient.name || ingredient.item || "",
    quantity: "1",
    unit: "item",
  })).filter((item) => item.name.trim());

  setRecipeGroceryTitle(recipe.name || recipe.title || "Recipe");
  setPendingRecipeIngredients(ingredients);
  goTo("groceries");
}
  async function confirmRecipeGroceries() {
  const validIngredients = pendingRecipeIngredients.filter(
    (item) => item.name.trim() && Number(item.quantity) > 0
  );

  if (validIngredients.length === 0) {
    setError("Please enter a valid quantity for at least one ingredient.");
    return;
  }

  setAddingRecipeGroceries(true);
  setError("");

  try {
    for (const item of validIngredients) {
      const alreadyExists = groceries.some(
        (grocery) =>
          grocery.name.trim().toLowerCase() ===
          item.name.trim().toLowerCase()
      );

      if (alreadyExists) continue;

      await request("/groceries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: item.name.trim(),
          quantity: Number(item.quantity),
          unit: item.unit,
        }),
      });
    }

    setPendingRecipeIngredients([]);
    setRecipeGroceryTitle("");
    await loadData();
  } catch (err) {
    setError(err.message);
  } finally {
    setAddingRecipeGroceries(false);
  }
}
  async function toggleGrocery(item) {
    try {
      await request(`/groceries/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checked: !item.checked }),
      });

      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteGrocery(id) {
    try {
      await request(`/groceries/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }
  async function editGrocery(id, quantity, unit) {
  try {
    await request(`/groceries/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quantity: Number(quantity),
        unit: unit.trim(),
      }),
    });

    await loadData();
  } catch (err) {
    setError(err.message);
    throw err;
  }
}
  // Open the laptop webcam.
  async function openWebcam() {
    setCameraError("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError(
        "Your browser does not support webcam access. Use HTTPS or localhost."
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
        },
        audio: false,
      });

      streamRef.current = stream;
      setCameraOpen(true);
    } catch (error) {
      setCameraError(
        error.name === "NotAllowedError"
          ? "Camera permission was denied. Please allow camera access in your browser."
          : error.name === "NotFoundError"
          ? "No webcam was detected on this device."
          : "Unable to access the webcam. Check your camera connection and permissions."
      );
    }
  }

  // Stop the webcam when the user closes the preview.
  function closeWebcam() {
    streamRef.current?.getTracks().forEach((track) => track.stop());

    streamRef.current = null;
    setCameraOpen(false);
  }

  // Capture a photo from the laptop webcam.
  function captureWebcamPhoto() {
    const video = videoRef.current;

    if (!video || !video.videoWidth) {
      setCameraError("The webcam is not ready yet. Please wait.");
      return;
    }

    if (files.length >= 8) {
      setCameraError("You can select a maximum of 8 photos.");
      return;
    }

    const canvas = document.createElement("canvas");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");

    if (!context) {
      setCameraError("Unable to capture the photo. Please try again.");
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setCameraError("Unable to capture the photo. Please try again.");
          return;
        }

        const photo = new File(
          [blob],
          `fridge-webcam-${Date.now()}.jpg`,
          { type: "image/jpeg" }
        );

        setFiles((old) => [...old, photo].slice(0, 8));

        closeWebcam();
        setCameraError("");
      },
      "image/jpeg",
      0.9
    );
  }

  async function scanFridge(event) {
    event.preventDefault();

    if (!files.length) {
      setError("Choose at least one fridge photo before scanning.");
      return;
    }

    const form = new FormData();

    files.slice(0, 8).forEach((file) => {
      form.append("files", file);
    });

    setScanning(true);
    setError("");
    setScanResult(null);

    try {
      const result = await request("/scan", {
        method: "POST",
        body: form,
      });

      setScanResult(result);
      setFiles([]);

      if (fileInput.current) {
        fileInput.current.value = "";
      }

      if (cameraInput.current) {
        cameraInput.current.value = "";
      }

      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  }

  const goTo = (id) => {
    setPage(id);
    setMobileMenu(false);
    setError("");
  };

  const pageTitle = {
    dashboard: "Your kitchen, at a glance",
    inventory: "Your food inventory",
    scan: "Scan your fridge",
    groceries: "Your grocery list",
    recipes: "Recipe inspiration",
  }[page];

  return (
    <>
      <div
        className={`intro-scene ${
          introPlaying ? "intro-playing" : "intro-finished"
        }`}
        aria-hidden="true"
      >
        <video
          ref={introVideoRef}
          className="intro-video"
          src="/fridge-intro.mp4"
          autoPlay
          muted
          playsInline
          preload="auto"
          onEnded={() => setIntroPlaying(false)}
        />

        {introPlaying && (
          <button
            type="button"
            className="intro-skip"
            onClick={() => {
              introVideoRef.current?.pause();
              setIntroPlaying(false);
            }}
            aria-label="Skip introduction"
          >
            Skip intro <ArrowUpRight size={15} />
          </button>
        )}
      </div>

      <div
        className={`app-reveal ${
          introPlaying ? "app-reveal-hidden" : "app-reveal-visible"
        }`}
      >
        <div className="app-shell">
          {mobileMenu && (
            <button
              className="mobile-overlay"
              onClick={() => setMobileMenu(false)}
              aria-label="Close menu"
            />
          )}

          <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
            <div className="brand">
              <div className="brand-icon">
                <Refrigerator size={25} />
              </div>

              <div>
                <strong>
                  fridge<span>scan</span>
                </strong>
                <small>YOUR SMART KITCHEN</small>
              </div>

              <button
                className="mobile-close"
                onClick={() => setMobileMenu(false)}
                aria-label="Close menu"
              >
                <X />
              </button>
            </div>

            <div className="nav-caption">WORKSPACE</div>

            <nav className="main-nav">
              {navigation.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  className={`nav-item ${page === id ? "active" : ""}`}
                  onClick={() => goTo(id)}
                >
                  <Icon size={19} strokeWidth={1.9} />

                  <span>{label}</span>

                  {id === "groceries" && pendingGroceries.length > 0 && (
                    <span className="nav-count">
                      {pendingGroceries.length}
                    </span>
                  )}
                </button>
              ))}
            </nav>

            <div className="sidebar-bottom">
              <div className="tip-card">
                <div className="tip-icon">
                  <Leaf size={18} />
                </div>

                <strong>Little steps matter</strong>

                <p>
                  Use what you have before buying more. Your wallet and the
                  planet will thank you.
                </p>
              </div>

              <div className="sidebar-status">
                <span /> Local kitchen workspace
              </div>
            </div>
          </aside>

          <main className="main-area">
            <header className="topbar">
              <button
                className="mobile-menu"
                onClick={() => setMobileMenu(true)}
                aria-label="Open menu"
              >
                <Menu />
              </button>

              <div className="breadcrumb">
                Workspace <span>/</span>{" "}
                <strong>
                  {navigation.find((n) => n.id === page)?.label || "Overview"}
                </strong>
              </div>

              <div className="topbar-actions">
                <div className="status-pill">
                  <span /> Connected locally
                </div>

                <button
                  className="icon-button"
                  onClick={loadData}
                  title="Refresh data"
                  aria-label="Refresh data"
                >
                  <RefreshCw size={18} />
                </button>
              </div>
            </header>

            <div className="page-content">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <Sparkles size={14} /> YOUR PERSONAL KITCHEN ASSISTANT
                  </div>

                  <h1>{pageTitle}</h1>

                  <p className="subtitle">
                    {page === "dashboard" &&
                      "Know what you have, plan what to eat, and waste less."}

                    {page === "inventory" &&
                      "Everything in your fridge and pantry, all in one place."}

                    {page === "scan" &&
                      "Upload a photo and let AI help identify your food."}

                    {page === "groceries" &&
                      "Keep track of what you need on your next shopping trip."}

                    {page === "recipes" && "Find inspiration for your next meal."}
                  </p>
                </div>

                <button
                  className="primary-button heading-button"
                  onClick={() => goTo("scan")}
                >
                  <ScanLine size={17} /> Scan fridge
                </button>
              </div>

              {error && (
                <div className="error-banner">
                  <AlertTriangle size={18} />
                  <span>{error}</span>
                  <button
                    onClick={() => setError("")}
                    aria-label="Dismiss"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}

              {loading ? (
                <div className="loading-state">
                  <RefreshCw className="spin" size={24} />
                  <p>Loading your kitchen...</p>
                </div>
              ) : (
                <>
                  {page === "dashboard" && (
                    <>
                      <section className="welcome-banner">
                        <div className="welcome-copy">
                          <div className="welcome-label">
                            <span className="sparkle-dot">✦</span> A FRESH START
                          </div>

                          <h2>
                            A happier fridge
                            <br />
                            starts right here.
                          </h2>

                          <p>
                            Make the most of what's already in your kitchen.
                          </p>

                          <button
                            className="light-button"
                            onClick={() => goTo("scan")}
                          >
                            Scan my fridge <ArrowUpRight size={16} />
                          </button>
                        </div>

                        <div className="welcome-art" aria-hidden="true">
                          <div className="art-circle circle-one" />
                          <div className="art-circle circle-two" />
                          <div className="food-emoji emoji-apple">🍎</div>
                          <div className="food-emoji emoji-avocado">🥑</div>
                          <div className="food-emoji emoji-carrot">🥕</div>
                          <div className="food-emoji emoji-leaf">🌿</div>
                          <div className="art-caption">
                            FRESH • SIMPLE • SMART
                          </div>
                        </div>
                      </section>

                      <section className="stats-grid">
                        <div className="stat-card">
                          <div className="stat-icon mint">
                            <Refrigerator size={20} />
                          </div>
                          <div className="stat-label">
                            Items in your kitchen
                          </div>
                          <div className="stat-number">{inventory.length}</div>
                          <div className="stat-foot">Tracked food items</div>
                        </div>

                        <div className="stat-card">
                          <div className="stat-icon peach">
                            <AlertTriangle size={20} />
                          </div>
                          <div className="stat-label">Running low</div>
                          <div className="stat-number">{lowStock.length}</div>
                          <div className="stat-foot">Items to check</div>
                        </div>

                        <div className="stat-card">
                          <div className="stat-icon lavender">
                            <ShoppingBasket size={20} />
                          </div>
                          <div className="stat-label">
                            On your grocery list
                          </div>
                          <div className="stat-number">
                            {pendingGroceries.length}
                          </div>
                          <div className="stat-foot">Things to pick up</div>
                        </div>

                        <div className="stat-card">
                          <div className="stat-icon yellow">
                            <ChefHat size={20} />
                          </div>
                          <div className="stat-label">Recipe ideas</div>
                          <div className="stat-number">{recipes.length}</div>
                          <div className="stat-foot">Ready for inspiration</div>
                        </div>
                      </section>

                      <div className="content-grid">
                        <section className="panel inventory-panel">
                          <div className="panel-heading">
                            <div>
                              <h3>Recently tracked food</h3>
                              <p>A quick look inside your kitchen</p>
                            </div>

                            <button
                              className="text-button"
                              onClick={() => goTo("inventory")}
                            >
                              View all <ArrowUpRight size={15} />
                            </button>
                          </div>

                          {inventory.length === 0 ? (
                            <EmptyState
                              icon={Refrigerator}
                              title="Your inventory is empty"
                              text="Add an item or scan your fridge to get started."
                            />
                          ) : (
                            <div className="food-list">
                              {inventory.slice(0, 5).map((item) => (
                                <FoodRow
                                  key={item.id ?? item.name}
                                  item={item}
                                  onDelete={deleteFood}
                                  onEdit={editInventory}
                                />
                              ))}
                            </div>
                          )}
                        </section>

                        <section className="panel grocery-panel">
                          <div className="panel-heading">
                            <div>
                              <h3>Shopping list</h3>
                              <p>Don't forget the essentials</p>
                            </div>

                            <button
                              className="round-action"
                              onClick={() => goTo("groceries")}
                              aria-label="Open grocery list"
                            >
                              <ArrowUpRight size={17} />
                            </button>
                          </div>

                          <form className="grocery-add-form" onSubmit={addGrocery}>
  <div className="grocery-add-heading">
    <div>
      <h3>Add an item to your shopping list</h3>
      <p>Enter the ingredient and review its quantity.</p>
    </div>
    <ShoppingBasket size={22} />
  </div>

  <div className="grocery-add-fields">
    <div className="grocery-name-field">
      <label htmlFor="grocery-name">Item name</label>
      <input
        id="grocery-name"
        type="text"
        value={newGrocery}
        onChange={(e) => setNewGrocery(e.target.value)}
        placeholder="e.g. Bread"
        required
      />
    </div>

    <div className="grocery-quantity-field">
      <label htmlFor="grocery-quantity">Quantity</label>
      <input
        id="grocery-quantity"
        type="number"
        min="0.1"
        step="0.1"
        value={newGroceryQuantity}
        onChange={(e) => setNewGroceryQuantity(e.target.value)}
        required
      />
    </div>

    <div className="grocery-unit-field">
      <label htmlFor="grocery-unit">Unit</label>
      <select
        id="grocery-unit"
        value={newGroceryUnit}
        onChange={(e) => setNewGroceryUnit(e.target.value)}
      >
        <option value="item">Item</option>
        <option value="piece">Piece</option>
        <option value="pack">Pack</option>
        <option value="loaf">Loaf</option>
        <option value="kg">Kg</option>
        <option value="g">Grams</option>
        <option value="litre">Litre</option>
        <option value="ml">ML</option>
        <option value="dozen">Dozen</option>
      </select>
    </div>
  </div>

  <button type="submit" className="primary-button grocery-add-submit">
    <Plus size={17} />
    Add to grocery list
  </button>
</form>

                          {pendingGroceries.length === 0 ? (
                            <EmptyState
                              icon={ShoppingBasket}
                              title="All caught up!"
                              text="Add items you need for your next shop."
                            />
                          ) : (
                            <div className="grocery-list compact-list">
                              {pendingGroceries.slice(0, 5).map((item) => (
                                <GroceryRow
                                  key={item.id ?? item.name}
                                  item={item}
                                  onToggle={toggleGrocery}
                                  onDelete={deleteGrocery}
                                  onEdit={editGrocery}
                                />
                              ))}
                            </div>
                          )}
                        </section>
                      </div>

                      <section className="panel">
                        <div className="panel-heading">
                          <div>
                            <h3>Make something delicious</h3>
                            <p>Ideas for your next meal</p>
                          </div>

                          <button
                            className="text-button"
                            onClick={() => goTo("recipes")}
                          >
                            Explore recipes <ArrowUpRight size={15} />
                          </button>
                        </div>

                        {recipes.length === 0 ? (
                          <EmptyState
                            icon={ChefHat}
                            title="Your next favourite meal awaits"
                            text="Your recipe suggestions will appear here when available."
                          />
                        ) : (
                          <div className="recipe-grid">
                            {recipes.slice(0, 3).map((recipe, i) => (
                              <RecipeCard
                                key={recipe.id ?? recipe.name ?? i}
                                recipe={recipe}
                                onAddMissing={prepareRecipeGroceries}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    </>
                  )}

                  {page === "inventory" && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h3>All food items</h3>
                          <p>{inventory.length} items currently tracked</p>
                        </div>

                        <form className="inventory-add-form" onSubmit={addFood}>
  <input
    value={newFood}
    onChange={(e) => setNewFood(e.target.value)}
    placeholder="Add food..."
    aria-label="New food item"
    required
  />

  <input
    type="number"
    min="0.1"
    step="0.1"
    value={newFoodQuantity}
    onChange={(e) => setNewFoodQuantity(e.target.value)}
    aria-label="Food quantity"
    required
  />

  <select
    value={newFoodUnit}
    onChange={(e) => setNewFoodUnit(e.target.value)}
    aria-label="Food unit"
  >
    <option value="item">Item</option>
    <option value="piece">Piece</option>
    <option value="pack">Pack</option>
    <option value="kg">Kg</option>
    <option value="g">Grams</option>
    <option value="litre">Litre</option>
    <option value="ml">ML</option>
    <option value="dozen">Dozen</option>
  </select>

  <button type="submit" aria-label="Add food">
    <Plus size={19} />
  </button>
</form>
                      </div>

                      <div className="search-box">
                        <Search size={17} />
                        <input
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          placeholder="Search your inventory..."
                        />
                      </div>

                      {visibleInventory.length === 0 ? (
                        <EmptyState
                          icon={Refrigerator}
                          title="No matching food items"
                          text="Try another search or add a new item."
                        />
                      ) : (
                        <div className="food-list full-list">
                          {visibleInventory.map((item) => (
                            <FoodRow
                              key={item.id ?? item.name}
                              item={item}
                              onDelete={deleteFood}
                            />
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {page === "scan" && (
                    <section className="panel scan-panel">
                      <div className="scan-intro">
                        <div className="scan-big-icon">
                          <ScanLine size={29} />
                        </div>

                        <h3>What's inside your fridge?</h3>

                        <p>
                          Upload up to 8 clear photos of your fridge or pantry.
                          Your existing AI backend will analyse them.
                        </p>
                      </div>

                      <form onSubmit={scanFridge}>
                        <button
                          type="button"
                          className="upload-zone"
                          onClick={() => fileInput.current?.click()}
                        >
                          <div className="upload-icon">
                            <ImagePlus size={26} />
                          </div>

                          <strong>
                            {files.length
                              ? `${files.length} photo${
                                  files.length > 1 ? "s" : ""
                                } selected`
                              : "Drop your photos here or browse"}
                          </strong>

                          <span>
                            JPG, PNG or WEBP · Up to 8 photos · 10 MB each
                          </span>

                          <span className="browse-label">Choose photos</span>
                        </button>

                        {/* Camera and gallery buttons */}
                        <div className="scan-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={() => {
                              const isTouchDevice = window.matchMedia(
                                "(pointer: coarse)"
                              ).matches;

                              if (isTouchDevice) {
                                cameraInput.current?.click();
                              } else {
                                openWebcam();
                              }
                            }}
                          >
                            <Camera size={17} />
                            Take photo
                          </button>

                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() => fileInput.current?.click()}
                          >
                            <Upload size={17} />
                            Choose from gallery
                          </button>
                        </div>

                        {cameraError && (
                          <p className="camera-error">{cameraError}</p>
                        )}

                        {/* Laptop webcam preview */}
                        {cameraOpen && (
                          <div className="camera-panel">
                            <video
                              ref={videoRef}
                              className="camera-preview"
                              autoPlay
                              muted
                              playsInline
                            />

                            <div className="scan-actions">
                              <button
                                type="button"
                                className="primary-button"
                                onClick={captureWebcamPhoto}
                              >
                                <Camera size={17} />
                                Capture photo
                              </button>

                              <button
                                type="button"
                                className="secondary-button"
                                onClick={closeWebcam}
                              >
                                <X size={17} />
                                Close camera
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Gallery file input */}
                        <input
                          ref={fileInput}
                          className="hidden-input"
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          multiple
                          onChange={(e) => {
  const selectedFiles = Array.from(e.target.files || []);

  console.log("Selected files:", selectedFiles);

  setFiles((old) => [...old, ...selectedFiles].slice(0, 8));

  e.target.value = "";
}}
                        />

                        {/* Mobile rear-camera input */}
                        <input
                          ref={cameraInput}
                          className="hidden-input"
                          type="file"
                          accept="image/*"
                          capture="environment"
                          onChange={(e) => {
                            const photo = e.target.files?.[0];

                            if (photo) {
                              setFiles((old) => [...old, photo].slice(0, 8));
                            }

                            e.target.value = "";
                          }}
                        />

                       {files.length > 0 && (
  <div className="selected-files">
    {files.map((file, i) => (
      <div
        className="selected-file"
        key={`${file.name}-${i}`}
      >
        <img
          src={filePreviews[i]?.url}
          alt={file.name}
          className="selected-image-preview"
        />

        <div className="selected-file-details">
          <span>{file.name}</span>
          <small>
            {(file.size / (1024 * 1024)).toFixed(2)} MB
          </small>
        </div>

        <button
          type="button"
          onClick={() =>
            setFiles((old) =>
              old.filter((_, index) => index !== i)
            )
          }
          aria-label={`Remove ${file.name}`}
        >
          <X size={15} />
        </button>
      </div>
    ))}
  </div>
)}
                        <button
                          className="primary-button scan-submit"
                          type="submit"
                          disabled={scanning || files.length === 0}
                        >
                          {scanning ? (
                            <>
                              <RefreshCw className="spin" size={17} />
                              Analysing photos...
                            </>
                          ) : (
                            <>
                              <Sparkles size={17} />
                              Scan my fridge
                            </>
                          )}
                        </button>
                      </form>

                      {scanResult && (
                        <div className="scan-result">
                          <div className="result-title">
                            <Check size={19} />
                            <strong>Scan completed</strong>
                          </div>

                          <p>
                            {scanResult.message ||
                              `Found ${
                                scanResult.count ??
                                scanResult.foods?.length ??
                                0
                              } food items.`}
                          </p>

                          <div className="result-chips">
                            {(scanResult.foods || []).map((food, i) => (
                              <span
                                key={`${
                                  food.item || food.name || food
                                }-${i}`}
                              >
                                {typeof food === "string"
                                  ? food
                                  : food.item || food.name || "Food item"}
                              </span>
                            ))}
                          </div>

                          <button
                            className="text-button"
                            onClick={() => goTo("inventory")}
                          >
                            View inventory <ArrowUpRight size={15} />
                          </button>
                        </div>
                      )}
                    </section>
                  )}

                  {page === "groceries" && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h3>Your shopping list</h3>
                          <p>
                            {pendingGroceries.length} items left to pick up
                          </p>
                        </div>
                      </div>
                      {pendingRecipeIngredients.length > 0 && (
  <div className="recipe-grocery-confirmation">
    <div className="panel-heading">
      <div>
        <h3>Add ingredients for {recipeGroceryTitle}</h3>
        <p>Check the quantity before adding them to your list.</p>
      </div>
    </div>

    <div className="recipe-grocery-fields">
      {pendingRecipeIngredients.map((item, index) => (
        <div className="recipe-grocery-field" key={`${item.name}-${index}`}>
          <strong>{item.name}</strong>

          <input
            type="number"
            min="0.1"
            step="0.1"
            value={item.quantity}
            aria-label={`Quantity of ${item.name}`}
            onChange={(e) => {
              const value = e.target.value;
              setPendingRecipeIngredients((old) =>
                old.map((ingredient, i) =>
                  i === index
                    ? { ...ingredient, quantity: value }
                    : ingredient
                )
              );
            }}
          />

          <select
            value={item.unit}
            aria-label={`Unit for ${item.name}`}
            onChange={(e) => {
              const value = e.target.value;
              setPendingRecipeIngredients((old) =>
                old.map((ingredient, i) =>
                  i === index
                    ? { ...ingredient, unit: value }
                    : ingredient
                )
              );
            }}
          >
            <option value="item">Item</option>
            <option value="piece">Piece</option>
            <option value="pack">Pack</option>
            <option value="kg">Kg</option>
            <option value="g">Grams</option>
            <option value="litre">Litre</option>
            <option value="ml">ML</option>
            <option value="loaf">Loaf</option>
          </select>

          <button
            type="button"
            className="row-delete"
            aria-label={`Remove ${item.name}`}
            onClick={() =>
              setPendingRecipeIngredients((old) =>
                old.filter((_, i) => i !== index)
              )
            }
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>

    <div className="recipe-grocery-actions">
      <button
        type="button"
        className="primary-button"
        disabled={addingRecipeGroceries || pendingRecipeIngredients.length === 0}
        onClick={confirmRecipeGroceries}
      >
        {addingRecipeGroceries
          ? "Adding ingredients..."
          : "Confirm and add to grocery list"}
      </button>

      <button
        type="button"
        className="secondary-button"
        disabled={addingRecipeGroceries}
        onClick={() => {
          setPendingRecipeIngredients([]);
          setRecipeGroceryTitle("");
        }}
      >
        Cancel
      </button>
    </div>
  </div>
)}
                      <form
  className="inline-add wide-add"
  onSubmit={addGrocery}
>
  <input
    value={newGrocery}
    onChange={(e) => setNewGrocery(e.target.value)}
    placeholder="What do you need to buy?"
    aria-label="New grocery item"
    required
  />

  <input
    type="number"
    min="0.1"
    step="0.1"
    value={newGroceryQuantity}
    onChange={(e) => setNewGroceryQuantity(e.target.value)}
    placeholder="Qty"
    aria-label="Grocery quantity"
    required
  />

  <select
    value={newGroceryUnit}
    onChange={(e) => setNewGroceryUnit(e.target.value)}
    aria-label="Grocery unit"
  >
    <option value="item">Item</option>
    <option value="piece">Piece</option>
    <option value="pack">Pack</option>
    <option value="kg">Kg</option>
    <option value="g">Grams</option>
    <option value="litre">Litre</option>
    <option value="ml">ML</option>
    <option value="dozen">Dozen</option>
  </select>

  <button type="submit">
    <Plus size={19} /> Add item
  </button>
</form>

                      {groceries.length === 0 ? (
                        <EmptyState
                          icon={ShoppingBasket}
                          title="Your list is ready for ideas"
                          text="Add the things you need to buy."
                        />
                      ) : (
                        <div className="grocery-list full-list">
                          {groceries.map((item) => (
                            <GroceryRow
                              key={item.id ?? item.name}
                              item={item}
                              onToggle={toggleGrocery}
                              onDelete={deleteGrocery}
                              onEdit={editGrocery}
                            />
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {page === "recipes" && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h3>Recipe ideas for you</h3>
                          <p>Suggestions provided by your current backend</p>
                        </div>
                      </div>

                      {recipes.length === 0 ? (
                        <EmptyState
                          icon={ChefHat}
                          title="No recipes available yet"
                          text="Your recipe suggestions will appear here when available."
                        />
                      ) : (
                        <div className="recipe-grid recipe-grid-large">
                          {recipes.map((recipe, i) => (
                           <RecipeCard
                            key={recipe.id ?? recipe.name ?? i}
                            recipe={recipe}
                            onAddMissing={prepareRecipeGroceries}
                          />
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  <footer className="page-footer">
                    <span>
                      <Leaf size={15} /> Less waste, more goodness.
                    </span>

                    <span>
                      Fridge Scan <span className="footer-dot">•</span> Local
                      development
                    </span>
                  </footer>
                </>
              )}
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
function FoodRow({ item, onDelete, onEdit }) {
  const [isEditing, setIsEditing] = useState(false);
  const [quantity, setQuantity] = useState(item.quantity ?? 1);
  const [unit, setUnit] = useState(item.unit || "item");

  const status = stockLabel(item);

  const iconByCategory = {
    vegetables: "🥦",
    fruit: "🍎",
    fruits: "🍎",
    dairy: "🥛",
    meat: "🍗",
    protein: "🥚",
    pantry: "🌾",
    bakery: "🍞",
    beverages: "🥤",
  };

  const category = String(item.category || "").toLowerCase();
  const emoji = iconByCategory[category] || "🥗";

  async function handleSave() {
    const parsedQuantity = Number(quantity);

    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      return;
    }

    if (!unit.trim()) {
      return;
    }

    await onEdit(item.id, parsedQuantity, unit.trim());
    setIsEditing(false);
  }

  function handleCancel() {
    setQuantity(item.quantity ?? 1);
    setUnit(item.unit || "item");
    setIsEditing(false);
  }

  return (
    <div className="food-row">
      <div className="food-emoji">{emoji}</div>

      <div className="food-details">
        <strong>{item.name}</strong>

        {isEditing ? (
          <div className="inline-add">
            <input
              type="number"
              min="0.01"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />

            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            >
              {["item", "kg", "g", "L", "ml", "pack", "bottle", "box"].map(
                (option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                )
              )}
            </select>

            <button type="button" onClick={handleSave}>
              Save
            </button>

            <button type="button" onClick={handleCancel}>
              Cancel
            </button>
          </div>
        ) : (
          <span>
            {item.category || "Other"} · Qty: {item.quantity ?? 1}{" "}
            {item.unit || "item"}
          </span>
        )}
      </div>

      <span className={`stock-badge ${status.toLowerCase()}`}>
        {status}
      </span>

      {!isEditing && (
        <button
          className="row-edit"
          onClick={() => setIsEditing(true)}
          title={`Edit ${item.name}`}
          aria-label={`Edit ${item.name}`}
        >
          Edit
        </button>
      )}

      <button
        className="row-delete"
        onClick={() => onDelete(item.id)}
        title={`Delete ${item.name}`}
        aria-label={`Delete ${item.name}`}
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}
function GroceryRow({ item, onToggle, onDelete, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [quantity, setQuantity] = useState(String(item.quantity ?? 1));
  const [unit, setUnit] = useState(item.unit || "item");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    const parsedQuantity = Number(quantity);

    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      return;
    }

    setSaving(true);

    try {
      await onEdit(item.id, parsedQuantity, unit);
      setEditing(false);
    } catch {
      // The parent displays the API error.
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setQuantity(String(item.quantity ?? 1));
    setUnit(item.unit || "item");
    setEditing(false);
  }

  return (
    <div className={`grocery-row ${item.checked ? "grocery-checked" : ""}`}>
      <button
        className={`check-button ${item.checked ? "checked" : ""}`}
        onClick={() => onToggle(item)}
        aria-label={item.checked ? "Mark as not done" : "Mark as done"}
      >
        {item.checked && <Check size={14} />}
      </button>

      <span className="grocery-name">{item.name}</span>

      {editing ? (
        <div className="grocery-edit-fields">
          <input
            type="number"
            min="0.1"
            step="0.1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            aria-label={`Quantity of ${item.name}`}
          />

          <select
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            aria-label={`Unit for ${item.name}`}
          >
            <option value="item">Item</option>
            <option value="piece">Piece</option>
            <option value="pack">Pack</option>
            <option value="loaf">Loaf</option>
            <option value="kg">Kg</option>
            <option value="g">Grams</option>
            <option value="litre">Litre</option>
            <option value="litres">Litres</option>
            <option value="ml">ML</option>
            <option value="dozen">Dozen</option>
          </select>

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            title="Save changes"
            aria-label="Save changes"
          >
            {saving ? "Saving..." : "Save"}
          </button>

          <button
            type="button"
            onClick={handleCancel}
            disabled={saving}
            title="Cancel editing"
            aria-label="Cancel editing"
          >
            Cancel
          </button>
        </div>
      ) : (
        <>
          <span className="grocery-quantity">
            {item.quantity ?? 1} {item.unit || "item"}
          </span>

          <button
            type="button"
            className="secondary-button"
            onClick={() => setEditing(true)}
            aria-label={`Edit ${item.name}`}
          >
            Edit
          </button>
        </>
      )}

      <button
        className="row-delete"
        onClick={() => onDelete(item.id)}
        aria-label={`Delete ${item.name}`}
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}


function RecipeCard({ recipe, onAddMissing }) {
  const name = recipe.name || recipe.title || "Recipe idea";

  const usedIngredients = Array.isArray(recipe.used_ingredients)
    ? recipe.used_ingredients
    : Array.isArray(recipe.ingredients)
      ? recipe.ingredients
      : [];

  const missingIngredients = Array.isArray(
    recipe.additional_ingredients_needed
  )
    ? recipe.additional_ingredients_needed
    : Array.isArray(recipe.missing_ingredients)
      ? recipe.missing_ingredients
      : [];

  const instructions = Array.isArray(recipe.instructions)
    ? recipe.instructions
    : [];

  const description =
    recipe.description ||
    recipe.summary ||
    "A delicious way to use ingredients from your kitchen.";

  return (
    <article className="recipe-card">
      <div className="recipe-art">
        <span>{["🥗", "🍲", "🍝", "🥘"][name.length % 4]}</span>

        <div className="recipe-art-tag">
          <Sparkles size={12} /> AI SUGGESTION
        </div>
      </div>

      <div className="recipe-info">
        <h4>{name}</h4>

        <p>{description}</p>

        {usedIngredients.length > 0 && (
          <div className="recipe-ingredient-section">
            <strong>✓ Available in your fridge</strong>

            <div className="ingredient-tags">
              {usedIngredients.map((ingredient, i) => (
                <span key={i}>
                  {typeof ingredient === "string"
                    ? ingredient
                    : ingredient.name || ingredient.item || "Ingredient"}
                </span>
              ))}
            </div>
          </div>
        )}

        {missingIngredients.length > 0 && (
  <div className="recipe-ingredient-section missing-ingredients">
    <strong>＋ Missing ingredients</strong>

    <div className="ingredient-tags">
      {missingIngredients.map((ingredient, i) => (
        <span key={i}>
          {typeof ingredient === "string"
            ? ingredient
            : ingredient.name || ingredient.item || "Ingredient"}
        </span>
      ))}
    </div>

    <button
      type="button"
      className="secondary-button recipe-add-button"
      onClick={() => onAddMissing(recipe)}
    >
      <ShoppingBasket size={16} />
      Add missing ingredients
    </button>
  </div>
)}

        {instructions.length > 0 && (
          <div className="recipe-instructions">
            <strong>How to prepare</strong>

            <ol>
              {instructions.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
        )}

        <div className="recipe-meta">
          <span>
            <Clock3 size={14} /> AI-generated recipe
          </span>
          <ChefHat size={16} />
        </div>
      </div>
    </article>
  );
}

function EmptyState({ icon: Icon, title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={23} />
      </div>

      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

export default App;