#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple HTTP server in Python.

Author: Gabriele Ranzari 0001123397
Date: 23 June 2025
"""

import socket
import os
import mimetypes
import urllib.parse
import base64

# Configuration
HOST = '127.0.0.1'
PORT = 8080
WEB_ROOT = './www'
SUBMISSIONS_FILE = 'submissions.txt'

# Admin credentials
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin'

def getMimeType(path):
    """
    Determine the MIME type of a file based on its extension.

    Args:
        path (str): File path to analyze.

    Returns:
        str: MIME type string or default for unknown types.
    """
    mimeType, _ = mimetypes.guess_type(path)
    return mimeType or 'application/octet-stream'

def sendResponse(client, statusCode, statusText, headers, bodyBytes):
    """
    Send a full HTTP response to the client.

    Args:
        client (socket):   The client socket connection.
        statusCode (int):  HTTP status code to send.
        statusText (str):  Status message (e.g., 'OK').
        headers (dict):    Dictionary of header names and values.
        bodyBytes (bytes): Response body in bytes.
    """
    responseLines = [f"HTTP/1.1 {statusCode} {statusText}"]
    for key, value in headers.items():
        responseLines.append(f"{key}: {value}")
    response = "\r\n".join(responseLines) + "\r\n\r\n"
    client.sendall(response.encode('utf-8') + bodyBytes)

def serveFile(filePath, client):
    """
    Read and send a static file to the client.

    Args:
        filePath (str):  Path to the requested file.
        client (socket): Client socket to send data to.
    """
    with open(filePath, 'rb') as file:
        content = file.read()
    mime = getMimeType(filePath)
    headers = {
        "Content-Type": f"{mime}; charset=utf-8",
        "Content-Length": str(len(content)),
    }
    sendResponse(client, 200, "OK", headers, content)

def handleGet(path, client):
    """
    Handle GET requests, serving static files or 404 page.

    Args:
        path (str):      The requested URL path.
        client (socket): Client socket to respond to.
    """
    if path == '/':
        path = '/index.html'
    filePath = os.path.join(WEB_ROOT, path.lstrip('/'))
    if os.path.isfile(filePath):
        serveFile(filePath, client)
    else:
        errorPage = os.path.join(WEB_ROOT, '404.html')
        if os.path.isfile(errorPage):
            serveFile(errorPage, client)
        else:
            body = b"<h1>404 Not Found</h1><p>The requested page does not exist.</p>"
            headers = {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Length": str(len(body))
            }
            sendResponse(client, 404, "Not Found", headers, body)

def handlePost(path, headersBlock, body, client):
    """
    Handle POST requests for the contact form only.

    Args:
        path (str):         The requested URL path.
        headersBlock (str): Raw HTTP request headers.
        body (str):         Initial request body.
        client (socket):    Client socket to respond to.
    """
    if path != '/contact':
        body = b"<h1>404 Not Found</h1>"
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body))
        }
        sendResponse(client, 404, "Not Found", headers, body)
        return

    contentLength = 0
    for line in headersBlock.splitlines():
        if line.lower().startswith('content-length:'):
            contentLength = int(line.split(':', 1)[1].strip())

    # Ensure full body is read
    while len(body.encode('utf-8')) < contentLength:
        body += client.recv(2048).decode('utf-8')

    data = urllib.parse.parse_qs(body)
    name = data.get('name', [''])[0]
    email = data.get('email', [''])[0]
    message = data.get('message', [''])[0]

    with open(SUBMISSIONS_FILE, 'a', encoding='utf-8') as file:
        file.write(f"Name: {name}\nEmail: {email}\nMessage: {message}\n---\n")

    thankYouPath = os.path.join(WEB_ROOT, 'thankyou.html')
    if os.path.isfile(thankYouPath):
        serveFile(thankYouPath, client)
    else:
        body = b"<h1>Thank you!</h1><p>Your message has been received.</p>"
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body))
        }
        sendResponse(client, 200, "OK", headers, body)

def promptAuth(client):
    """
    Send a 401 Unauthorized response with Basic Auth challenge.

    Args:
        client (socket): Client socket to respond to.
    """
    body = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Access denied</title>"
        "</head><body>"
        "<h1>🔒 Authentication Required</h1>"
        "<p>Please login to access the admin section.</p>"
        "<p><a href='/'>Return to Home</a></p>"
        "</body></html>"
    ).encode('utf-8')

    headers = {
        "WWW-Authenticate": 'Basic realm="Admin Area"',
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": str(len(body))
    }
    sendResponse(client, 401, "Unauthorized", headers, body)

def checkAuth(headersBlock):
    """
    Verify Basic Auth credentials from headers.

    Args:
        headersBlock (str): Raw HTTP request headers.

    Returns:
        bool: True if credentials match, False otherwise.
    """
    for line in headersBlock.splitlines():
        if line.lower().startswith('authorization:'):
            token = line.split(' ', 1)[1].strip()
            if token.startswith('Basic '):
                credentials = base64.b64decode(token.split()[1]).decode('utf-8')
                username, password = credentials.split(':', 1)
                return username == ADMIN_USER and password == ADMIN_PASS
    return False

def serveAdmin(client):
    """
    Serve admin page with form submissions.

    Args:
        client (socket): Client socket to respond to.
    """
    templatePath = os.path.join(WEB_ROOT, 'admin.html')
    with open(templatePath, encoding='utf-8') as f:
        template = f.read()

    entriesHtml = []
    if os.path.isfile(SUBMISSIONS_FILE):
        with open(SUBMISSIONS_FILE, encoding='utf-8') as f:
            rawText = f.read().strip()
        for i, block in enumerate(rawText.split('---'), 1):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            card = ["<div class='card mb-3'><div class='card-body'>",
                    f"<h5 class='card-title'># {i}</h5>"]
            for line in lines:
                card.append(f"<p class='card-text'>{line}</p>")
            card.append("</div></div>")
            entriesHtml.append("\n".join(card))

    fullPage = template.replace("<!-- ENTRIES -->", "\n".join(entriesHtml))
    body = fullPage.encode('utf-8')
    headers = {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": str(len(body))
    }
    sendResponse(client, 200, "OK", headers, body)

def handleRequest(client, address):
    """
    Main entry point: parse requests and dispatch handlers.

    Args:
        client (socket): Client connection socket.
        address (tuple): Client address info.
    """
    try:
        raw = client.recv(4096).decode('utf-8', errors='ignore')
        if not raw:
            client.close()
            return

        firstLine = raw.splitlines()[0]
        print(f"[{address}] {firstLine}")

        headersBlock, body = (raw.split('\r\n\r\n', 1) + [''])[:2]
        method, path, _ = headersBlock.splitlines()[0].split()

        if method == 'GET' and path == '/admin':
            if not checkAuth(headersBlock):
                promptAuth(client)
            else:
                serveAdmin(client)
            client.close()
            return

        if method == 'GET':
            handleGet(path, client)
        elif method == 'POST':
            handlePost(path, headersBlock, body, client)
        else:
            body = b"<h1>405 Method Not Allowed</h1>"
            headers = {"Content-Type": "text/html; charset=utf-8",
                       "Content-Length": str(len(body))}
            sendResponse(client, 405, "Method Not Allowed", headers, body)

        client.close()

    except Exception as e:
        print(f"Error handling request from {address}: {e}")
        # Serve 500 page if available
        try:
            errorPath = os.path.join(WEB_ROOT, '500.html')
            if os.path.isfile(errorPath):
                with open(errorPath, 'rb') as f:
                    body = f.read()
                headers = {"Content-Type": "text/html; charset=utf-8",
                           "Content-Length": str(len(body))}
                sendResponse(client, 500, "Internal Server Error", headers, body)
            else:
                body = b"<h1>500 Internal Server Error</h1>"
                headers = {"Content-Type": "text/html; charset=utf-8",
                           "Content-Length": str(len(body))}
                sendResponse(client, 500, "Internal Server Error", headers, body)
        except Exception as nested:
            print(f"Error sending 500 response: {nested}")
        finally:
            client.close()

def startServer():
    """
    Start socket server and listen for incoming connections.
    """
    print(f"Server listening at http://{HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen(5)
        while True:
            client, address = server.accept()
            handleRequest(client, address)

if __name__ == "__main__":
    startServer()