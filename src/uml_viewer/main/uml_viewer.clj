(ns uml-viewer.main.uml-viewer
  (:require [uml-viewer.adapters.core :as core]
            [uml-viewer.clojure-language.source-clojure]
            [uml-viewer.languages.external :as external])
  (:gen-class))

(defn -main [& args]
  (let [lang (external/detect-lang ".")]
    (when (#{:python :typescript} lang)
      (external/write-agent-md! "." lang))
    (apply core/start! (external/dispatch-source) args)))
