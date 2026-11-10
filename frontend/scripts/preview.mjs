import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { dirname, extname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const port = Number(process.argv[2] || 5501);
const tipos = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml" };
createServer(async (req, res) => {
    try {
        if (!["GET", "HEAD"].includes(req.method)) { res.writeHead(405).end(); return; }
        const ruta = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
        let archivo = resolve(root, "." + ruta);
        const dentro = relative(root, archivo);
        if (dentro.startsWith("..") || isAbsolute(dentro) || dentro.split(/[\\/]/).some(parte => parte.startsWith("."))) { res.writeHead(403).end(); return; }
        if ((await stat(archivo)).isDirectory()) archivo = resolve(archivo, "index.html");
        const datos = await stat(archivo);
        if (!datos.isFile()) { res.writeHead(404).end(); return; }
        res.writeHead(200, { "Content-Type": tipos[extname(archivo)] || "application/octet-stream", "Content-Length": datos.size, "Cache-Control": "no-store" });
        if (req.method === "HEAD") { res.end(); return; }
        createReadStream(archivo).on("error", () => res.destroy()).pipe(res);
    } catch { res.writeHead(404).end("No encontrado"); }
}).listen(port, "127.0.0.1", () => process.stdout.write("Vista previa: http://127.0.0.1:" + port + "/\n"));
