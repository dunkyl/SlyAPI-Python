let module_name = document.getElementsByTagName("section")[0].id.replace(/^module-/, "");
let module_access_re = new RegExp(`${module_name}\.`, 'g');

let descs = document.getElementsByTagName("dd");

let classes = document.querySelectorAll("dl.py.class");

for (let cls of classes) {
    cls.innerHTML = cls.innerHTML.replace(module_access_re, "");
}

for (let desc of descs) {
    let first = desc.firstChild;
    if (first && first.textContent.startsWith("Bases:")) {
        let link = first.children[0];
        let code = link.children[0];
        let span = code.children[0];
        let text = span.textContent;

        // remove `Bases: object` from doc pages
        if (text == "object") {
            first.remove();
        } // convert `Bases: abc.ABC` to abstract class
        else if (text == "abc.ABC") {
            let a = document.createElement('a');
            a.href = "https://docs.python.org/3/library/abc.html#abc.ABC";
            a.textContent = "abscract class";
            desc.parentElement.children[0].children[0].children[0].textContent = "";
            desc.parentElement.children[0].children[0].children[0].appendChild(a);
            first.remove();
        }
        else if (text == "Generic") {
            let elem = document.createElement('span');
            let generic_arg = first.children[1].children[0].textContent;
            elem.textContent = `[ ${generic_arg} ]`;
            desc.parentElement.children[0].appendChild(elem);
        } // TODO: case for remove RETURN TYPE: None

    }
}



