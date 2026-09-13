// api/ip.ts
import type { VercelRequest, VercelResponse } from '@vercel/node';

export default function handler(req: VercelRequest, res: VercelResponse) {
    // 1. 优先从 x-forwarded-for 获取（Vercel 默认会带上此头，格式为 "真实IP, 代理IP1, 代理IP2"）
    let clientIp = (req.headers['x-forwarded-for'] as string)?.split(',')[0]?.trim();

    // 2. 如果没有，尝试从 x-real-ip 获取
    if (!clientIp) {
        clientIp = req.headers['x-real-ip'] as string;
    }

    // 3. 如果还没有，尝试从 socket 获取（通常在内网环境备用）
    if (!clientIp) {
        clientIp = req.socket.remoteAddress;
    }

    // 4. 清理 IPv6 格式的前缀（例如 Node.js 经常会返回 "::ffff:110.86.212.136"）
    if (clientIp && clientIp.startsWith('::ffff:')) {
        clientIp = clientIp.replace('::ffff:', '');
    }

    // 5. 处理本地开发环境的情况
    if (clientIp === '::1' || clientIp === '127.0.0.1') {
        clientIp = '本地环境 (127.0.0.1)';
    }

    // 6. 禁止缓存，确保每次刷新都能拿到最新的 IP
    res.setHeader('Cache-Control', 'no-store, max-age=0');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    
    res.status(200).json({
        ipv4: clientIp || 'null',
        ts: Date.now()
    });
}