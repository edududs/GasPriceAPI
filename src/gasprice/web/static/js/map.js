// Choropleth of Brazil's states. Data comes from the #map-data JSON the server renders inside #board,
// so every htmx swap of the board recolours the map without a second request.
(() => {
  const COLORS = ["#fff7bc", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02"];
  const element = document.getElementById("map");
  if (!element || !window.L) return;

  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const map = L.map(element, {
    zoomSnap: 0.25,
    scrollWheelZoom: false,
    attributionControl: false,
  });
  let layer = null;
  let data = null;
  let selected = element.dataset.selected || null;

  const readData = () => {
    const node = document.getElementById("map-data");
    data = node ? JSON.parse(node.textContent) : null;
  };

  const money = (value) =>
    value.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
      minimumFractionDigits: data.places,
      maximumFractionDigits: data.places,
    });

  const range = () => {
    const values = Object.values(data?.prices ?? {});
    return values.length ? [Math.min(...values), Math.max(...values)] : [0, 0];
  };

  const color = (value) => {
    if (value === undefined) return css("--map-empty");
    const [low, high] = range();
    const share = high > low ? (value - low) / (high - low) : 0.5;
    return COLORS[Math.min(COLORS.length - 1, Math.floor(share * COLORS.length))];
  };

  const style = (feature) => {
    const uf = feature.properties.uf;
    const isSelected = uf === selected;
    return {
      fillColor: color(data?.prices[uf]),
      fillOpacity: 1,
      color: isSelected ? css("--map-selected") : css("--map-stroke"),
      weight: isSelected ? 2.5 : 1,
    };
  };

  const tooltip = (uf) => {
    const price = data?.prices[uf];
    const name = data?.names[uf] ?? uf;
    return price === undefined ? `${name}: sem dados` : `<strong>${name}</strong><br>${money(price)}`;
  };

  const renderLegend = () => {
    const legend = document.getElementById("map-legend");
    if (!legend || !data) return;
    const [low, high] = range();
    const empty = Object.keys(data.prices).length === 0;
    legend.querySelector("[data-low]").textContent = empty ? "—" : money(low);
    legend.querySelector("[data-high]").textContent = empty ? "—" : money(high);
  };

  const refresh = () => {
    if (!layer) return;
    layer.setStyle(style);
    layer.eachLayer((shape) => {
      shape.setTooltipContent(tooltip(shape.feature.properties.uf));
      if (shape.feature.properties.uf === selected) shape.bringToFront();
    });
    renderLegend();
  };

  const loadState = (uf) => {
    const url = element.dataset.stateUrl.replace("__UF__", uf);
    htmx.ajax("GET", `${url}?fuel=${data.fuel}`, { target: "#state-detail", swap: "innerHTML" });
    const params = new URLSearchParams({ fuel: data.fuel, state: uf });
    history.replaceState(history.state, "", `?${params}`);
  };

  const select = (uf) => {
    selected = uf;
    refresh();
    loadState(uf);
  };

  readData();
  fetch(element.dataset.geojson)
    .then((response) => response.json())
    .then((geojson) => {
      layer = L.geoJSON(geojson, {
        style,
        onEachFeature: (feature, shape) => {
          const uf = feature.properties.uf;
          shape.bindTooltip(tooltip(uf), { sticky: true, direction: "top" });
          shape.on({
            click: () => select(uf),
            mouseover: () => shape.setStyle({ weight: 2.5 }),
            mouseout: () => layer.resetStyle(shape),
          });
        },
      }).addTo(map);
      map.fitBounds(layer.getBounds(), { padding: [8, 8] });
      refresh();
    });

  // Ranking rows and anything else marked with data-state select a state the same way the map does.
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-select-state]");
    if (trigger) select(trigger.dataset.selectState);
  });

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target.id !== "board") return;
    readData();
    refresh();
    if (selected) loadState(selected);
  });

  new ResizeObserver(() => map.invalidateSize()).observe(element);
})();
