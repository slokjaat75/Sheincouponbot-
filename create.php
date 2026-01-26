<?php
header("Content-Type: application/json");

echo json_encode([
  "status" => "success",
  "message" => "Payment link created (TEST MODE)",
  "amount" => $_GET['amount'] ?? 0
]);
