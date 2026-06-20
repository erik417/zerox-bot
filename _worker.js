export default {
  async fetch(request) {
    const url = new URL(request.url);
    const apiUrl = "https://api.telegram.org" + url.pathname + url.search;
    return fetch(apiUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });
  }
}
