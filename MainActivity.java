package com.omidwar.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.widget.Toast;

public class MainActivity extends Activity {
    // Replace this with the final HTTPS address after the online server is deployed.
    private static final String APP_URL = "https://YOUR-OMIDWAR-DOMAIN.example";
    private WebView webView;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        setContentView(webView);
        if (APP_URL.contains("YOUR-OMIDWAR-DOMAIN")) {
            Toast.makeText(this, "ابتدا آدرس HTTPS سایت امیدوار را در MainActivity.java وارد کنید.", Toast.LENGTH_LONG).show();
        } else {
            webView.loadUrl(APP_URL);
        }
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }
}
