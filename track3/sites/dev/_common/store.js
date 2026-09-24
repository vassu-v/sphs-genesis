/*
 * store.js — tiny shared cart/state helper for the dev fixture sites.
 *
 * Not part of the guard or the oracle contract — just enough vanilla-JS
 * plumbing so every family can share one honest checkout flow
 * (product -> cart -> checkout -> /order/confirmed) while layering its
 * own traps on top. Each site runs on its own port/origin so
 * localStorage is naturally isolated between sites.
 */
(function (global) {
  "use strict";

  var KEY = "bodyguard_cart_v1";

  function getRunId() {
    try {
      var params = new URLSearchParams(global.location.search);
      return params.get("run_id") || "unknown";
    } catch (e) {
      return "unknown";
    }
  }

  function url(path) {
    var rid = getRunId();
    if (rid === "unknown") return path;
    var sep = path.indexOf("?") === -1 ? "?" : "&";
    return path + sep + "run_id=" + encodeURIComponent(rid);
  }

  function go(path) {
    global.location.href = url(path);
  }

  function emptyCart() {
    return { item: null, extras: {}, marketingOptIn: false, placed: false };
  }

  function getCart() {
    try {
      var raw = global.localStorage.getItem(KEY);
      if (!raw) return emptyCart();
      var parsed = JSON.parse(raw);
      return Object.assign(emptyCart(), parsed);
    } catch (e) {
      return emptyCart();
    }
  }

  function setCart(cart) {
    try {
      global.localStorage.setItem(KEY, JSON.stringify(cart));
    } catch (e) {
      /* ignore */
    }
  }

  function resetCart() {
    try {
      global.localStorage.removeItem(KEY);
    } catch (e) {
      /* ignore */
    }
  }

  function setItem(sku, name, price) {
    var cart = getCart();
    cart.item = { sku: sku, name: name, price: price };
    setCart(cart);
    return cart;
  }

  // extra: { label, price (cents, 0 for non-monetary), active, recurring }
  function setExtra(key, extra) {
    var cart = getCart();
    cart.extras[key] = Object.assign(
      { label: key, price: 0, active: false, recurring: false },
      cart.extras[key] || {},
      extra
    );
    setCart(cart);
    return cart;
  }

  function total(cart) {
    cart = cart || getCart();
    var t = cart.item ? cart.item.price : 0;
    Object.keys(cart.extras).forEach(function (k) {
      var e = cart.extras[k];
      if (e.active) t += e.price;
    });
    return t;
  }

  function activeRecurring(cart) {
    cart = cart || getCart();
    return Object.keys(cart.extras).filter(function (k) {
      return cart.extras[k].active && cart.extras[k].recurring;
    });
  }

  function formatPrice(cents, currency) {
    currency = currency || "INR";
    var symbol = currency === "INR" ? "₹" : currency + " ";
    return symbol + (cents / 1).toLocaleString("en-IN");
  }

  global.Store = {
    getRunId: getRunId,
    url: url,
    go: go,
    getCart: getCart,
    setCart: setCart,
    resetCart: resetCart,
    setItem: setItem,
    setExtra: setExtra,
    total: total,
    activeRecurring: activeRecurring,
    formatPrice: formatPrice,
  };
})(window);
