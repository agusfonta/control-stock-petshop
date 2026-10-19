# ARCA — datos a conseguir para C-11 (facturación electrónica)

Estado: C-11 **sin implementar**. Se difiere hasta tener los datos fiscales de la dueña. Este documento deja listo qué pedir y cómo cargarlo, para que el cambio posterior sea solo configuración.

## 1. Datos a pedirle a la dueña

| Dato | Para qué | Notas |
|---|---|---|
| CUIT del titular | Emisor de los comprobantes | Persona física o jurídica |
| Condición frente al IVA | Define los tipos de comprobante | Monotributo → Factura C; Responsable Inscripto → A/B |
| Punto(s) de venta | Numeración de comprobantes | Debe ser de tipo "RECE para aplicativo y web services" (no el de controlador fiscal) |
| Clave fiscal (nivel 3) | Solo para que ella (o su contador) genere el certificado | **No pasarla por chat ni guardarla en el repo** |
| Certificado `.crt` + clave privada `.key` | Autenticación WSAA | Los genera ella/contador desde "Administración de Certificados Digitales"; adherir el servicio WSFE |
| Domicilio y razón social | Encabezado del ticket/factura | |
| Tipos de comprobante a emitir | Alcance de US-002 | ¿Solo C? ¿A/B? ¿Notas de crédito por anulación? (pregunta Media abierta en la KB) |

## 2. Cómo se cargarán (cuando lleguen)

Solo por variables de entorno, nunca en el repo (regla dura del proyecto):

```
ARCA_CUIT=
ARCA_PUNTO_VENTA=
ARCA_CERT=      # ruta al .crt
ARCA_KEY=       # ruta al .key
ARCA_ENV=homologacion|produccion
```

Los certificados viven fuera del repo (secrets del host en producción; ver `knowledge-base/08_arquitectura_propuesta.md`).

## 3. Qué queda para C-11 (no hecho)

Ver [CHANGES.md](../CHANGES.md) §C-11: outbox, `ComprobanteFE`, worker con reintentos, endpoints `facturar` / `comprobantes` / `reintentar`, badge de estado en el frontend, tests.

Alcance sugerido al retomar, en dos tandas: (1) todo contra un cliente ARCA simulado (interfaz `ClienteARCA` + fake); (2) cliente real contra homologación y, con los datos de ella, producción.

## 4. Mientras tanto

- La venta ya funciona sin factura; el ticket interno se emite igual.
- Para probar contra homologación hace falta un CUIT con clave fiscal propio (no el de la dueña).
