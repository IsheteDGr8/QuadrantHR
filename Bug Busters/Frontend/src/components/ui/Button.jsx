function Button({
  variant = "secondary",
  size,
  block,
  as: As = "button",
  className = "",
  ...rest
}) {
  const classes = [
    "btn",
    `btn-${variant}`,
    size === "sm" ? "btn-sm" : "",
    block ? "btn-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <As className={classes} {...rest} />;
}

export default Button;
