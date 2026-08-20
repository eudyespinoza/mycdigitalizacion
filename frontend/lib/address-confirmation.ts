export function buildAddressConfirmation(latitude: number, longitude: number, address_choice: "written" | "reverse") {
  return { latitude: latitude.toFixed(7), longitude: longitude.toFixed(7), address_choice };
}
