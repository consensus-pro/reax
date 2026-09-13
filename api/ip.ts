// api/ip.ts
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { networkInterfaces } from 'node:os';

/**
 * 直接读取当前服务器（Node 进程所在主机）的 IPv4 地址。
 * 不请求任何第三方 API。
 * 优先返回非 internal（非回环）的 IPv4。
 */
function getServerIPv4(): string {
    const nets = networkInterfaces();
    const list: string[] = [];

    for (const name of Object.keys(nets)) {
        for (const net of nets[name] ?? []) {
            // Node 18+ 是 'IPv4' 字符串，旧版本是数字 4
            const family = typeof net.family === 'string'
                ? net.family
                : `IPv${net.family}`;

            if (family !== 'IPv4') continue;
            if (net.internal) continue;

            list.push(net.address);
        }
    }

    return list[0] ?? '127.0.0.1';
}

export default function handler(_req: VercelRequest, res: VercelResponse) {
    res.setHeader('Cache-Control', 'no-store, max-age=0');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.status(200).json({
        ipv4: getServerIPv4(),
        ts: Date.now()
    });
}