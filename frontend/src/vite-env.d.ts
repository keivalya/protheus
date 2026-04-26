/// <reference types="vite/client" />

declare module "html2pdf.js" {
  const html2pdf: () => {
    from: (element: HTMLElement) => {
      set: (options: object) => {
        save: () => Promise<void>;
      };
    };
  };
  export default html2pdf;
}
