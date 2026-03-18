window.initAllMaps = function () {
  // ===== event detail map =====
  const detailMapEl = document.getElementById("event-detail-map");

  if (detailMapEl && window.google && google.maps) {
    const lat = parseFloat(detailMapEl.dataset.lat);
    const lng = parseFloat(detailMapEl.dataset.lng);

    if (!isNaN(lat) && !isNaN(lng)) {
      const map = new google.maps.Map(detailMapEl, {
        center: { lat: lat, lng: lng },
        zoom: 14,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
      });

      new google.maps.Marker({
        position: { lat: lat, lng: lng },
        map: map,
      });
    }
  }

  // ===== event form map =====
  const formMapEl = document.getElementById("event-map");

  if (formMapEl && window.google && google.maps) {
    const latInput = document.getElementById("id_latitude");
    const lngInput = document.getElementById("id_longitude");
    const locationInput = document.getElementById("id_location_name");
    const coordsText = document.getElementById("selected-coords");
    const useMyLocationBtn = document.getElementById("use-my-location");

    if (!latInput || !lngInput || !coordsText) {
      return;
    }

    const defaultCenter = { lat: 55.8721, lng: -4.2890 };

    const existingLat = parseFloat(latInput.value);
    const existingLng = parseFloat(lngInput.value);

    const startPosition = (!isNaN(existingLat) && !isNaN(existingLng))
      ? { lat: existingLat, lng: existingLng }
      : defaultCenter;

    const map = new google.maps.Map(formMapEl, {
      center: startPosition,
      zoom: 15,
      streetViewControl: false,
      mapTypeControl: false,
      fullscreenControl: false,
    });

    const marker = new google.maps.Marker({
      position: startPosition,
      map: map,
      draggable: true,
      title: "Event location",
    });

    if (isNaN(existingLat) || isNaN(existingLng)) {
      marker.setMap(null);
      coordsText.textContent = "No coordinates selected yet.";
    } else {
      coordsText.textContent = `Selected: ${existingLat.toFixed(6)}, ${existingLng.toFixed(6)}`;
    }

    function updatePosition(lat, lng) {
      latInput.value = lat.toFixed(6);
      lngInput.value = lng.toFixed(6);
      coordsText.textContent = `Selected: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;

      if (!marker.getMap()) {
        marker.setMap(map);
      }

      marker.setPosition({ lat: lat, lng: lng });
      map.panTo({ lat: lat, lng: lng });
    }

    map.addListener("click", function (e) {
      if (!e.latLng) return;
      updatePosition(e.latLng.lat(), e.latLng.lng());
    });

    marker.addListener("dragend", function (e) {
      if (!e.latLng) return;
      updatePosition(e.latLng.lat(), e.latLng.lng());
    });

    if (useMyLocationBtn) {
      useMyLocationBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
          coordsText.textContent = "Geolocation is not supported in this browser.";
          return;
        }

        coordsText.textContent = "Getting your current location...";

        navigator.geolocation.getCurrentPosition(
          function (position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            updatePosition(lat, lng);

            if (locationInput && !locationInput.value.trim()) {
              locationInput.value = "Current selected location";
            }
          },
          function () {
            coordsText.textContent = "Could not get your current location. You can still place the marker manually.";
          },
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0,
          }
        );
      });
    }
  }
};