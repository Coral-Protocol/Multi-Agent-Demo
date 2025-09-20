
import type { RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ url }) => {
    const query = url.searchParams.get('q');
    if (!query) {
        return new Response(JSON.stringify({ error: 'Missing query parameter' }), { status: 400 });
    }

    try {
        // Replace with the host you want to fetch from
        const targetHost = 'http://localhost:8000/search';
        const fetchUrl = `${targetHost}?q=${encodeURIComponent(query)}`;


        const res = await fetch(fetchUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ q: query })
        });
        const data = await res.json(); // use .json() if the response is JSON

        return new Response(JSON.stringify(data), {
            status: res.status,
            headers: {
                'Content-Type': res.headers.get('Content-Type') || 'text/plain'
            }
        });
    } catch (error) {
        return new Response(JSON.stringify({ error: 'Failed to fetch from target host' }), { status: 500 });
    }
};
