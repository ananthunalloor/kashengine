// Start the Swagger UI. This is a separate file because the Content-Security-Policy of the
// site does not allow inline scripts.
window.addEventListener("load", function () {
  var element = document.getElementById("swagger-ui");
  window.ui = SwaggerUIBundle({
    url: element.dataset.specUrl,
    dom_id: "#swagger-ui",
    deepLinking: true,
    // The API has only GET endpoints.
    supportedSubmitMethods: ["get"],
    tryItOutEnabled: true,
    persistAuthorization: false,
    requestInterceptor: function (request) {
      request.credentials = "same-origin";
      return request;
    },
  });
});
