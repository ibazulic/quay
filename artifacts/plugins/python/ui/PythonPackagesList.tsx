import React from "react";
import RepositoriesList from "src/routes/RepositoriesList/RepositoriesList";

export function PythonPackagesList() {
  return (
    <>
      <RepositoriesList
        organizationName={null}
        repoKind={"python"}
        title={"Python Packages"}
      />
    </>
  );
}
