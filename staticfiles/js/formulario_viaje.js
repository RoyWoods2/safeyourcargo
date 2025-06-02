document.addEventListener("DOMContentLoaded", function () {
  const modoTransporte = document.getElementById("modoTransporte");

  const vueloOrigenPais = document.getElementById("vueloOrigenPais");
  const vueloOrigenCiudad = document.getElementById("vueloOrigenCiudad");
  const vueloDestinoPais = document.getElementById("vueloDestinoPais");
  const vueloDestinoCiudad = document.getElementById("vueloDestinoCiudad");

  const selectAeropuertoOrigen = document.getElementById("id_aeropuerto_origen");
  const selectAeropuertoDestino = document.getElementById("id_aeropuerto_destino");

  const paisOrigenRuta = document.getElementById("paisOrigen");
  const ciudadOrigenRuta = document.getElementById("ciudadOrigen");
  const paisDestinoRuta = document.getElementById("paisDestino");
  const ciudadDestinoRuta = document.getElementById("ciudadDestino");

  const paisesMap = {}; // CL -> Chile

  // 🔹 Cargar países y poblar todos los selects
  function cargarPaises() {
    fetch("/api/paises/")
      .then(response => response.json())
      .then(data => {
        if (data.paises) {
          data.paises.forEach(pais => {
            paisesMap[pais.codigo] = pais.nombre; // ✅ clave del fix

            const opt1 = new Option(pais.nombre, pais.codigo);
            const opt2 = new Option(pais.nombre, pais.codigo);
            if (vueloOrigenPais) vueloOrigenPais.appendChild(opt1);
            if (vueloDestinoPais) vueloDestinoPais.appendChild(opt2);

            const opt3 = new Option(pais.nombre, pais.codigo);
            const opt4 = new Option(pais.nombre, pais.codigo);
            if (paisOrigenRuta) paisOrigenRuta.appendChild(opt3);
            if (paisDestinoRuta) paisDestinoRuta.appendChild(opt4);
          });
        }
      })
      .catch(error => console.error("Error cargando países:", error));
  }

  // 🔹 Utilidad CSRF
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // 🔹 Cargar ciudades
  function cargarCiudades(nombrePais, select) {
    if (!nombrePais) return;
    select.innerHTML = '<option value="">Cargando ciudades...</option>';
    fetch("/api/ciudades/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify({ pais: nombrePais })
    })
      .then(res => res.json())
      .then(data => {
        select.innerHTML = '<option value="">Seleccione una ciudad</option>';
        (data.ciudades || []).forEach(ciudad => {
          const option = new Option(ciudad, ciudad);
          select.appendChild(option);
        });
      })
      .catch(() => {
        select.innerHTML = '<option value="">Error al cargar</option>';
      });
  }

  // 🔹 Cargar aeropuertos
  function cargarAeropuertos(nombrePais, select) {
    if (!nombrePais) return;
    select.innerHTML = '<option value="">Cargando aeropuertos...</option>';
    fetch("/api/aeropuertos/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify({ pais: nombrePais })
    })
      .then(res => res.json())
      .then(data => {
        select.innerHTML = '<option value="">Seleccione un aeropuerto</option>';
        (data.aeropuertos || []).forEach(a => {
          const option = new Option(`${a.name} (${a.city})`, a.iata);
          select.appendChild(option);
        });
      })
      .catch(() => {
        select.innerHTML = '<option value="">Error al cargar</option>';
      });
  }

  // 🔹 Cargar puertos marítimos
  function cargarPuertos(codigoPais, select) {
    if (!codigoPais) return;
    select.innerHTML = '<option value="">Cargando puertos...</option>';
    fetch("/api/unlocode/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify({ pais: codigoPais, function: "1" })
    })
      .then(res => res.json())
      .then(data => {
        select.innerHTML = '<option value="">Seleccione un puerto</option>';
        (data.ubicaciones || []).forEach(p => {
          const option = new Option(`${p.name} (${p.locode})`, p.locode);
          select.appendChild(option);
        });
      })
      .catch(() => {
        select.innerHTML = '<option value="">Error al cargar</option>';
      });
  }

  // 🔹 Eventos para DETALLES DE VIAJE
  vueloOrigenPais.addEventListener("change", () => {
    const codigo = vueloOrigenPais.value;
    const nombre = paisesMap[codigo] || "";
    cargarCiudades(nombre, vueloOrigenCiudad);

    const modo = modoTransporte.value;
    if (modo === "Aereo") {
      cargarAeropuertos(nombre, selectAeropuertoOrigen);
    } else if (modo === "Maritimo") {
      cargarPuertos(codigo, selectAeropuertoOrigen);
    }
  });

  vueloDestinoPais.addEventListener("change", () => {
    const codigo = vueloDestinoPais.value;
    const nombre = paisesMap[codigo] || "";
    cargarCiudades(nombre, vueloDestinoCiudad);

    const modo = modoTransporte.value;
    if (modo === "Aereo") {
      cargarAeropuertos(nombre, selectAeropuertoDestino);
    } else if (modo === "Maritimo") {
      cargarPuertos(codigo, selectAeropuertoDestino);
    }
  });

  // 🔹 Eventos para RUTA
  if (paisOrigenRuta && ciudadOrigenRuta) {
    paisOrigenRuta.addEventListener("change", () => {
      const paisNombre = paisOrigenRuta.options[paisOrigenRuta.selectedIndex].textContent;
      cargarCiudades(paisNombre, ciudadOrigenRuta);
    });
  }

  if (paisDestinoRuta && ciudadDestinoRuta) {
    paisDestinoRuta.addEventListener("change", () => {
      const paisNombre = paisDestinoRuta.options[paisDestinoRuta.selectedIndex].textContent;
      cargarCiudades(paisNombre, ciudadDestinoRuta);
    });
  }

  // 🔹 Ejecutar carga inicial
  cargarPaises();
  actualizarVistaTransporte();
  modoTransporte.addEventListener("change", actualizarVistaTransporte);
function actualizarVistaTransporte() {
  const modo = modoTransporte.value;

  const labelNombreTransporte = document.getElementById("label_nombre_transporte");
  const labelNumeroViaje = document.getElementById("label_numero_viaje");
  const labelAeropuertoOrigen = document.getElementById("label_aeropuerto_origen");
  const labelAeropuertoDestino = document.getElementById("label_aeropuerto_destino");

  const grupoAeropuertoOrigen = document.getElementById("grupo_aeropuerto_origen");
  const grupoAeropuertoDestino = document.getElementById("grupo_aeropuerto_destino");

  if (modo === "Aereo") {
    labelNombreTransporte.textContent = "Nombre Avión / Línea Aérea";
    labelNumeroViaje.textContent = "N° Viaje / Vuelo";
    labelAeropuertoOrigen.textContent = "Aeropuerto Origen";
    labelAeropuertoDestino.textContent = "Aeropuerto Destino";

    grupoAeropuertoOrigen.classList.remove("d-none");
    grupoAeropuertoDestino.classList.remove("d-none");
  } else if (modo === "Maritimo") {
    labelNombreTransporte.textContent = "Nombre Buque / Naviera";
    labelNumeroViaje.textContent = "N° Viaje / Travesía";
    labelAeropuertoOrigen.textContent = "Puerto de Origen";
    labelAeropuertoDestino.textContent = "Puerto de Destino";

    grupoAeropuertoOrigen.classList.remove("d-none");
    grupoAeropuertoDestino.classList.remove("d-none");
  } else if (modo === "TerrestreFerroviario") {
    labelNombreTransporte.textContent = "Nombre Vehículo / Línea Ferroviaria";
    labelNumeroViaje.textContent = "N° Viaje / Transporte";

    // 🔴 Ocultar completamente los contenedores de los "aeropuertos"
    grupoAeropuertoOrigen.classList.add("d-none");
    grupoAeropuertoDestino.classList.add("d-none");
  } else {
    // Otros casos
    labelNombreTransporte.textContent = "Nombre Transporte";
    labelNumeroViaje.textContent = "N° Viaje";

    grupoAeropuertoOrigen.classList.add("d-none");
    grupoAeropuertoDestino.classList.add("d-none");
  }
}


});
