function Tag({ variant = "neutral", className = "", children, ...rest }) {
  const classes = ["tag", `tag-${variant}`, className].filter(Boolean).join(" ");

  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  );
}

export default Tag;
