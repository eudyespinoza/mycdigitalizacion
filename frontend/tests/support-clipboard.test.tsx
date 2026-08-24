import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { AttachmentQueue, mergeAttachmentQueue } from "@/components/support/attachment-queue";
import { filesFromClipboard, MessageComposer } from "@/components/support/message-composer";

function clipboardWith(text: string, ...files: File[]) {
  return {
    clipboardData: {
      getData: (format: string) => format === "text/plain" ? text : "",
      items: [
        { kind: "string", getAsFile: () => null },
        ...files.map((file) => ({ kind: "file", getAsFile: () => file })),
        { kind: "file", getAsFile: () => null },
      ],
    },
  };
}

function textFile(name: string, size = 4) {
  return new File(["x".repeat(size)], name, { type: "text/plain", lastModified: 100 });
}

describe("adjuntos del compositor", () => {
  afterEach(() => vi.restoreAllMocks());

  test("pega una imagen sin cancelar el pegado nativo de texto", () => {
    render(<MessageComposer disabled={false} onSend={vi.fn()} />);
    const message = screen.getByLabelText("Mensaje");
    const image = new File(["png"], "captura.png", { type: "image/png" });

    const pasteWasNotCancelled = fireEvent.paste(message, clipboardWith("Detalle", image));
    // JSDOM does not perform the browser's native text insertion for paste events.
    fireEvent.change(message, { target: { value: "Detalle" } });

    expect(pasteWasNotCancelled).toBe(true);
    expect(message).toHaveValue("Detalle");
    expect(screen.getByText("captura.png")).toBeVisible();
  });

  test("extrae únicamente archivos reales del portapapeles", () => {
    const image = new File(["png"], "captura.png", { type: "image/png" });
    expect(filesFromClipboard(clipboardWith("Detalle", image) as unknown as ClipboardEvent)).toEqual([image]);
  });

  test("no intercepta el menú nativo al hacer clic derecho", () => {
    render(<MessageComposer disabled={false} onSend={vi.fn()} />);
    expect(fireEvent.contextMenu(screen.getByLabelText("Mensaje"))).toBe(true);
  });

  test("rechaza el sexto adjunto antes de enviar", () => {
    const fiveFiles = Array.from({ length: 5 }, (_, index) => textFile(`nota-${index}.txt`));
    const result = mergeAttachmentQueue(fiveFiles, [textFile("sexta.txt")]);

    expect(result.error).toBe("Podés adjuntar hasta 5 archivos por mensaje.");
    expect(result.files).toEqual(fiveFiles);
  });

  test("rechaza archivos grandes y un total mayor a 30 MB", () => {
    const tooLarge = textFile("pesado.txt", 10 * 1024 * 1024 + 1);
    expect(mergeAttachmentQueue([], [tooLarge]).error).toBe("El archivo «pesado.txt» supera el máximo de 10 MB por archivo.");

    const almostTen = Array.from({ length: 4 }, (_, index) => textFile(`parte-${index}.txt`, 8 * 1024 * 1024));
    expect(mergeAttachmentQueue([], almostTen).error).toBe("Los adjuntos superan el máximo total de 30 MB por mensaje.");
  });

  test("acepta CSV sólo con el MIME que valida el servidor", () => {
    const accepted = new File(["producto,precio"], "precios.csv", { type: "text/csv" });
    expect(mergeAttachmentQueue([], [accepted])).toEqual({ files: [accepted] });

    ["application/csv", "application/vnd.ms-excel", ""].forEach((type) => {
      const rejected = new File(["producto,precio"], "precios.csv", { type });
      expect(mergeAttachmentQueue([], [rejected]).error).toBe("El archivo «precios.csv» no tiene un formato permitido.");
    });
  });

  test("revoca las vistas previas de imágenes al quitar archivos y al desmontarse", () => {
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: () => "" });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: () => undefined });
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:captura");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const image = new File(["png"], "captura.png", { type: "image/png" });
    const { rerender, unmount } = render(<AttachmentQueue files={[image]} onRemove={vi.fn()} />);

    expect(createObjectURL).toHaveBeenCalledWith(image);
    rerender(<AttachmentQueue files={[]} onRemove={vi.fn()} />);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:captura");
    unmount();
  });
});
