# =============================================================================
#  CVM Monitor PRO - Frontend (React 18 + Vite + Tailwind)
#  Multi-stage classico: Node so existe no estagio de build. A imagem final
#  nao tem Node, nem node_modules, nem codigo-fonte -- apenas o dist/ estatico
#  servido por nginx alpine. ~1,2 GB (node) -> ~50 MB (nginx).
# =============================================================================

# -----------------------------------------------------------------------------
# Estagio 1: deps -- instala node_modules a partir do lockfile
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

# Apenas os manifests: enquanto package.json/lock nao mudarem, o Docker
# reaproveita esta camada e o `npm ci` (o passo lento) nao roda de novo.
COPY frontend/package.json frontend/package-lock.json ./

# `npm ci` instala exatamente o que esta no lockfile -- build reproduzivel,
# diferente de `npm install`, que pode subir versoes de patch silenciosamente.
RUN npm ci --no-audit --no-fund

# -----------------------------------------------------------------------------
# Estagio 2: build -- gera o dist/ com Vite
# -----------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./

# NODE_ENV=production faz o Vite/Tailwind removerem o codigo de desenvolvimento
# e o Tailwind fazer purge das classes nao usadas.
ENV NODE_ENV=production

# vite.config.js separa react/react-dom e chart.js em chunks proprios: o
# navegador guarda os vendors em cache entre deploys e so rebaixa o chunk da
# aplicacao quando o codigo muda.
RUN npm run build \
    # Pre-compressao dos assets: o gzip_static do nginx entrega o .gz pronto,
    # sem gastar CPU por requisicao.
    && find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' \) \
        -exec gzip -9 -k {} \;

# -----------------------------------------------------------------------------
# Estagio 3: runtime -- nginx alpine servindo o dist/
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/app.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
