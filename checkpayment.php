<?php
header("Content-Type: application/json");

echo json_encode([
  "status" => "paid",
  "order_id" => $_GET['orderid'] ?? "NA"
]);
