function buildMap(selector, viewbox) {
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = "https://unpkg.com/leaflet@1.4.0/dist/leaflet.css"
  const script = document.createElement('script')
  script.src = "https://unpkg.com/leaflet@1.4.0/dist/leaflet.js"
  document.head.appendChild(link)
  document.head.appendChild(script)
  const map = L.map(selector).setView(viewbox[0], viewbox[1])
  L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoidGVycmFwZXV0ZXMiLCJhIjoiY2p0N3IxZjRhMDB5bDQ1cW52Z2s2MnVnNCJ9.Ism1OhdYA3qPFom2htkx8w', {
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
    maxZoom: 18,
    id: 'mapbox.streets',
    accessToken: 'pk.eyJ1IjoidGVycmFwZXV0ZXMiLCJhIjoiY2p0N3IxZjRhMDB5bDQ1cW52Z2s2MnVnNCJ9.Ism1OhdYA3qPFom2htkx8w'
  }).addTo(map)
  return map
}
