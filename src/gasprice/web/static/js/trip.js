// Trip planner map: click to add points, drag to adjust, and draw the route the server returns.
// The form posts the points as "lat,lon;lat,lon"; everything else on the page is htmx.
(() => {
  const element = document.getElementById("trip-map");
  if (!element || !window.L) return;

  const LETTERS = "ABCDEFGHIJ";
  const maxPoints = Number(element.dataset.maxPoints || 10);
  const input = document.getElementById("trip-points-input");
  const list = document.getElementById("trip-points");
  const result = document.getElementById("trip-result");

  const map = L.map(element, { zoomSnap: 0.5 }).setView([-15.8, -47.9], 4);
  if (element.dataset.tiles) {
    L.tileLayer(element.dataset.tiles, { maxZoom: 18, attribution: element.dataset.attribution }).addTo(map);
  }
  // State outlines: orientation even when tiles are unavailable, and the borders the cost is split by.
  fetch(element.dataset.states)
    .then((response) => response.json())
    .then((geojson) =>
      L.geoJSON(geojson, {
        interactive: false,
        style: { color: "#a8a29e", weight: 1, fill: false },
      }).addTo(map),
    );

  /** @type {{lat: number, lon: number, name: string | null, marker: L.Marker}[]} */
  let points = [];
  let routeLine = null;

  const icon = (letter, last) =>
    L.divIcon({
      className: "",
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      html: `<span class="grid size-7 place-items-center rounded-full border-2 border-white text-xs font-bold text-white shadow-md ${
        last ? "bg-emerald-600" : letter === "A" ? "bg-stone-900" : "bg-amber-500"
      }">${letter}</span>`,
    });

  const clearRoute = () => {
    if (routeLine) map.removeLayer(routeLine);
    routeLine = null;
  };

  const render = () => {
    points.forEach((point, index) => {
      point.marker.setIcon(icon(LETTERS[index], index === points.length - 1 && index > 0));
    });
    input.value = points.map((p) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`).join(";");
    list.replaceChildren(
      ...(points.length
        ? points.map((point, index) => {
            const item = document.createElement("li");
            item.className = "flex items-center gap-2";
            const role = index === 0 ? "Origem" : index === points.length - 1 ? "Destino" : "Parada";
            const label = point.name ?? `${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`;
            item.innerHTML = `
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-stone-100 text-xs font-bold dark:bg-stone-800">${LETTERS[index]}</span>
              <span class="min-w-0 flex-1"><span class="text-xs text-stone-500">${role}</span><span class="block truncate"></span></span>
              <button type="button" class="rounded px-1.5 text-stone-400 hover:text-red-600" aria-label="Remover ponto ${LETTERS[index]}">✕</button>`;
            item.querySelector(".truncate").textContent = label;
            item.querySelector("button").addEventListener("click", () => remove(index));
            return item;
          })
        : [Object.assign(document.createElement("li"), {
            className: "text-stone-500 dark:text-stone-400",
            textContent: "Nenhum ponto marcado ainda.",
          })]),
    );
  };

  const add = (lat, lon, name = null) => {
    if (points.length >= maxPoints) return;
    const marker = L.marker([lat, lon], { draggable: true }).addTo(map);
    const point = { lat, lon, name, marker };
    marker.on("dragend", () => {
      const position = marker.getLatLng();
      Object.assign(point, { lat: position.lat, lon: position.lng, name: null });
      clearRoute();
      render();
    });
    points.push(point);
    clearRoute();
    render();
  };

  const remove = (index) => {
    map.removeLayer(points[index].marker);
    points.splice(index, 1);
    clearRoute();
    render();
  };

  map.on("click", (event) => add(event.latlng.lat, event.latlng.lng));

  document.addEventListener("click", (event) => {
    const place = event.target.closest("[data-place-lat]");
    if (place) {
      const lat = Number(place.dataset.placeLat);
      const lon = Number(place.dataset.placeLon);
      add(lat, lon, place.dataset.placeName.split(",").slice(0, 2).join(","));
      map.setView([lat, lon], Math.max(map.getZoom(), 9));
      document.getElementById("place-results").replaceChildren();
      return;
    }
    const vehicle = event.target.closest("[data-vehicle-id]");
    if (vehicle) {
      document.getElementById("vehicle-id").value = vehicle.dataset.vehicleId;
      const selected = document.getElementById("vehicle-selected");
      selected.innerHTML = `<span class="font-medium"></span><span class="block text-xs text-stone-600 dark:text-stone-400"></span>`;
      selected.firstElementChild.textContent = vehicle.dataset.vehicleName;
      selected.lastElementChild.textContent = vehicle.dataset.vehicleDetail;
      selected.classList.remove("hidden");
      document.getElementById("vehicle-results").replaceChildren();
    }
  });

  document.querySelectorAll('input[name="mode"]').forEach((radio) =>
    radio.addEventListener("change", () => {
      document.querySelectorAll("[data-mode]").forEach((section) => {
        section.classList.toggle("hidden", section.dataset.mode !== radio.value);
      });
    }),
  );

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target !== result) return;
    clearRoute();
    const node = document.getElementById("route-data");
    if (!node) return;
    const { geometry } = JSON.parse(node.textContent);
    routeLine = L.polyline(geometry, { color: "#d97706", weight: 5, opacity: 0.9 }).addTo(map);
    map.fitBounds(routeLine.getBounds(), { padding: [24, 24] });
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  new ResizeObserver(() => map.invalidateSize()).observe(element);
})();
