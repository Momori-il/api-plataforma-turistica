import { escaparHTML as html } from "../utils/ui.js";

const dinero = valor => "$\u00a0" + Number(valor).toLocaleString("es-AR");

export function renderizarCalificacion(hotel) {
    if (hotel.calificacion === null || hotel.calificacion === undefined) {
        return '<span class="hotel-rating-empty">Sin calificación</span>';
    }
    const nota = Number(hotel.calificacion).toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return '<span class="hotel-rating">' + nota + '/5</span><span class="hotel-rating-caption">' + (hotel.datosSimulados ? "Calificación simulada" : "Calificación") + '</span>';
}

export function renderizarTarjetaHotel(hotel, { href, noches, habitaciones = 1 }) {
    const precio = hotel.precio > 0 ? dinero(hotel.precio) : "Consultar";
    const cantidad = habitaciones + (habitaciones === 1 ? " habitación" : " habitaciones");
    return `
        <article class="catalog-hotel">
            <a class="catalog-image" href="${html(href)}">
                <img src="${html(hotel.imagen)}" alt="${html(hotel.nombre)}" loading="lazy">
            </a>
            <div class="catalog-info">
                <span class="discovery-eyebrow">${html(hotel.categoria)}</span>
                <h3><a href="${html(href)}">${html(hotel.nombre)}</a></h3>
                <p>${html(hotel.ubicacion)}</p>
                ${Number(hotel.calificacion) > 0 ? `<div class="hotel-rating-row">${renderizarCalificacion(hotel)}</div>` : ""}
                <ul class="catalog-services">${hotel.servicios.map(servicio => "<li>" + html(servicio) + "</li>").join("")}</ul>
            </div>
            <div class="catalog-price">
                ${hotel.descuento > 0 ? '<span class="discount-label">−' + html(hotel.descuento) + '%</span>' : ""}
                ${hotel.precioAnterior > hotel.precio ? "<del>" + dinero(hotel.precioAnterior) + "</del>" : ""}
                <strong>${precio}</strong><small>por habitación y noche · ARS</small>
                ${noches && hotel.precio > 0 ? "<p>" + dinero(hotel.precio * noches * habitaciones) + " por " + noches + (noches === 1 ? " noche" : " noches") + "</p><small>" + cantidad + " · estimado</small>" : ""}
                <a class="catalog-detail" href="${html(href)}">Ver alojamiento</a>
            </div>
        </article>`;
}
